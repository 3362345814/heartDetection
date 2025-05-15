# -*- coding: utf-8 -*-
import base64
import datetime
import hashlib
import hmac
import json
import re
import time
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import quote

import requests


class XunfeiOCR:
    def __init__(self, app_id, api_key, api_secret):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.host = "api.xf-yun.com"
        self.url = "https://api.xf-yun.com/v1/private/sf8e6aca1"

    def _build_date(self):
        """生成RFC1123格式的时间戳"""
        return datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')

    def _build_signature(self, date):
        """生成签名"""
        signature_origin = f"host: {self.host}\ndate: {date}\nPOST /v1/private/sf8e6aca1 HTTP/1.1"
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature = base64.b64encode(signature_sha).decode('utf-8')
        return signature

    def _build_authorization(self, date):
        """生成authorization参数"""
        signature = self._build_signature(date)
        authorization_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        return authorization

    def _build_request_url(self, date, authorization):
        """构建完整的请求URL"""
        return (f"{self.url}?authorization={quote(authorization)}"
                f"&host={quote(self.host)}&date={quote(date)}")

    def _build_request_body(self, image_base64):
        """构建请求体"""
        return {
            "header": {
                "app_id": self.app_id,
                "status": 3
            },
            "parameter": {
                "sf8e6aca1": {
                    "category": "ch_en_public_cloud",
                    "result": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "json"
                    }
                }
            },
            "payload": {
                "sf8e6aca1_data_1": {
                    "encoding": "jpg",
                    "status": 3,
                    "image": image_base64
                }
            }
        }

    def _parse_ultrasound_data(self, text: str) -> Dict:
        """解析超声图像文本数据"""
        data = {
            'raw_text': text,
            'measurements': {},
            'parameters': {}
        }

        # 心房二维尺寸的处理
        if 'Dist' in text:
            dist_measurements = re.findall(r'Dist\s*(\d+\.\d{2})\s*cm', text)
            if len(dist_measurements) >= 4:
                # 如果有4个或更多的Dist值，认为是心房二维尺寸图
                data['measurements'].update({
                    'RA_length': float(dist_measurements[0]),
                    'RA_short': float(dist_measurements[1]),
                    'LA_length': float(dist_measurements[2]),
                    'LA_short': float(dist_measurements[3])
                })
            elif len(dist_measurements) == 1:
                # 如果只有1个Dist值，可能是TAPSE测量
                data['measurements']['TAPSE_dist'] = float(dist_measurements[0])

        # 左心室频谱多普勒图的参数
        if 'Decel Time' in text or 'E/A' in text:  # 左心室频谱多普勒图特有的标记
            parameters_to_find = {
                'EDT': r'(?:MV\s+)?Decel Time\s+(\d+)(?:\s*ms)?',  # 匹配 MV Decel Time 123 ms
                'E/A': r'(?:MV\s+)?E/A\s+(\d+\.?\d*)|EJA\s+(\d+\.?\d*)'  # 匹配 E/A 1.5 或 EJA 1.5
            }

            # 特殊处理 E/A，因为它可能以 EJA 形式出现
            ea_match = re.search(r'EJA\s+(\d+\.?\d*)', text)
            if ea_match:
                data['measurements']['E/A'] = float(ea_match.group(1))

        # 左心室组织多普勒图的参数
        elif 'Med E' in text or 'E Med E' in text:  # 放宽检查条件
            parameters_to_find = {
                # 对于 e_velocity，匹配 Med E 或 E Med 后面最近的数值
                'e_velocity': r'(?:Med\s*E|E\s*Med)\s*(?:Vel\s*)?(\d+\.?\d*)(?:\s*cm/?s)?',

                # 对于 E/Med E，更宽松地匹配任何形式的 E Med E 后面最近的数值
                'E_Med_E': r'(?:E/Med\s*E|E\s*Med\s*E|E/E)\s*(\d+\.?\d*)',

                # 对于 SV，保持原样但略微放宽
                'SV': r'SV\s*(\d+\.?\d*)(?:\s*ml)?'
            }

            # 如果常规匹配失败，尝试更宽松的匹配
            for param, pattern in parameters_to_find.items():
                match = re.search(pattern, text)
                if not match and param == 'E_Med_E':
                    # 如果没有找到E_Med_E，使用更宽松的模式：
                    # 在"E Med E"或类似文本后查找最近的数字
                    e_med_e_patterns = [
                        r'(?:E/Med\s*E|E\s*Med\s*E|E/E)[^\d]*?(\d+\.?\d*)',  # 尝试匹配任何E Med E形式后的数字
                        r'(?:E/Med|E\s*Med)[^\d]*?(\d+\.?\d*)',  # 尝试匹配E/Med或E Med后的数字
                        r'E/E[^\d]*?(\d+\.?\d*)'  # 尝试匹配E/E后的数字
                    ]

                    for alt_pattern in e_med_e_patterns:
                        match = re.search(alt_pattern, text)
                        if match:
                            break

                if match:
                    try:
                        value = float(match.group(1))
                        data['measurements'][param] = value
                    except (ValueError, IndexError):
                        continue
        # 右心室组织多普勒图的参数
        elif 'PG' in text:  # 右心室组织多普勒图特有的标记
            parameters_to_find = {
                'tr_velocity': r'Vel\s*(\d+(?:\.\d*)?)(?:\s*cm/s)?'
            }
        # 其他图像的参数
        else:
            parameters_to_find = {
                'EDV': r'EDV[^\d]*(\d+\.?\d*)(?:ml)?',
                'ESV': r'ESV[^\d]*(\d+\.?\d*)(?:ml)?',
                'LVEF': r'(?:LVEF|EF)[^\d]*(\d+\.?\d*)(?:\s*%)?',
                'FS': r'FS[^\d]*(\d+\.?\d*)(?:\s*%)?',
                'IVS': r'IVS[^\d]*(\d+\.?\d*)(?:mm)?'
            }

        for param, pattern in parameters_to_find.items():
            match = re.search(pattern, text)
            if match:
                try:
                    # 对于 E/A，需要检查是否有两个捕获组
                    if param == 'E/A' and match.lastindex and match.lastindex > 1:
                        # 使用非None的那个捕获组
                        value = match.group(1) if match.group(1) is not None else match.group(2)
                    else:
                        value = match.group(1)
                    data['measurements'][param] = float(value)
                except ValueError:
                    continue

        return data

    def recognize(self, image_path: str, max_retries=3) -> dict | None:
        """执行OCR识别并返回结构化数据"""
        for attempt in range(max_retries):
            try:
                with open(image_path, 'rb') as f:
                    image_base64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception as e:
                raise Exception(f"读取图片失败: {str(e)}")

            try:
                date = self._build_date()
                authorization = self._build_authorization(date)
                url = self._build_request_url(date, authorization)
                body = self._build_request_body(image_base64)

                response = requests.post(url, json=body)
                if response.status_code != 200:
                    raise Exception(f"请求失败: {response.status_code} - {response.text}")

                result = response.json()
                if result['header']['code'] != 0:
                    raise Exception(f"识别失败: {result['header']['message']}")

                text_base64 = result['payload']['result']['text']
                text_data = json.loads(base64.b64decode(text_base64).decode('utf-8'))

                recognized_text = []

                if 'pages' not in text_data:
                    raise Exception("返回数据格式错误：缺少'pages'字段")

                for page in text_data['pages']:
                    if 'lines' not in page:
                        continue

                    for line in page['lines']:
                        if 'words' not in line:
                            continue

                        for word in line['words']:
                            if 'content' in word:
                                recognized_text.append(word['content'])

                if not recognized_text:
                    raise Exception("未能识别到任何文本")

                return self._parse_ultrasound_data(' '.join(recognized_text))

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"第{attempt + 1}次识别失败，正在重试...")
                    time.sleep(1)
                    continue
                raise Exception(f"OCR识别失败: {str(e)}")
        return None


class UltrasoundReport:
    def __init__(self, current_time: str, user_login: str):
        self.current_time = current_time
        self.user_login = user_login
        self.image_types = [
            "心房二维尺寸图",
            "左心室M型超声图",
            "左心室组织多普勒图",
            "右心室M型超声图",
            "右心室组织多普勒图",
            "左心室频谱多普勒图"  # 添加新的图像类型
        ]
        self.data = {image_type: None for image_type in self.image_types}
        self.ocr = XunfeiOCR(
            app_id="7d5de13f",
            api_key="ed82f06d6a280479c849a8043dc7d0a0",
            api_secret="MTg2NjhiM2ZlZDY0ZTUxZjVhYmM1ZGIz"
        )

    def process_images(self, images):
        """
        处理从数据库中获取的图像实体列表
        参数:
            images: List[UltrasoundImage]
        """
        # 映射 image_type 到 image_type_name
        type_mapping = {
            4: "心房二维尺寸图",
            5: "左心室M型超声图",
            6: "右心室M型超声图",
            7: "左心室组织多普勒图",
            8: "右心室组织多普勒图",
            9: "左心室频谱多普勒图"
        }
        for image in images:
            image_type_name = type_mapping.get(getattr(image, 'image_type', None))
            if not image_type_name or image_type_name not in self.image_types:
                continue  # 跳过非目标图像类型
            try:
                result = self.ocr.recognize(getattr(image, 'file_path', ''))
                self.data[image_type_name] = result
                print(f"\n{image_type_name}识别结果:")
                print("原始文本:", result['raw_text'])
                if result['measurements']:
                    print("\n提取的测量值:")
                    for param, value in result['measurements'].items():
                        print(f"{param}: {value}")
            except Exception as e:
                print(f"处理{image_type_name}时出错: {str(e)}")

    def _get_tapse_value(self) -> Optional[float]:
        """
        获取TAPSE值，专门从右心室M型超声图中获取
        返回：原始TAPSE值，如果没有找到则返回None
        """
        if "右心室M型超声图" in self.data and self.data["右心室M型超声图"]:
            measurements = self.data["右心室M型超声图"].get('measurements', {})
            if 'TAPSE_dist' in measurements:
                return measurements['TAPSE_dist']  # 直接返回原始值，不进行四舍五入
        return None

    def _calculate_pulmonary_pressure(self, velocity: float) -> int:
        """
        计算肺动脉收缩压
        velocity: 速度 (cm/s)
        返回: 压力 (mmHg)
        """
        if velocity is None:
            return None

        # 打印调试信息
        print(f"Debug - Input velocity: {velocity} cm/s")

        # 1. 转换为m/s
        velocity_ms = velocity / 100
        print(f"Debug - Velocity in m/s: {velocity_ms}")

        # 2. 计算压力
        pressure = 4 * (velocity_ms ** 2) + 3
        print(f"Debug - Calculated pressure before rounding: {pressure}")

        # 3. 四舍五入到整数
        result = round(pressure)
        print(f"Debug - Final pressure: {result}")

        return result

    def _evaluate_chamber_size(self, measurements: Dict) -> str:
        normal_ranges = {
            'LA_short': (2.7, 4.0),
            'LA_length': (3.9, 5.0),
            'RA_short': (3.3, 4.0),
            'RA_length': (4.1, 5.1)
        }

        results = []
        if measurements.get('LA_short') > normal_ranges['LA_short'][1] or \
                measurements.get('LA_length') > normal_ranges['LA_length'][1]:
            results.append("左房扩大")
        if measurements.get('RA_short') > normal_ranges['RA_short'][1] or \
                measurements.get('RA_length') > normal_ranges['RA_length'][1]:
            results.append("右房扩大")

        return f"{', '.join(results)}，余房室腔大小正常。" if results else "各房室腔大小正常。"

    def _format_tapse(self, value: float) -> float:
        """格式化TAPSE值，进行四舍五入"""
        if value is None:
            return None
        # 在这里进行四舍五入，保留一位小数
        return round(value * 10) / 10

    def _get_measurement_value(self, param: str) -> Optional[float]:
        """从所有图像数据中获取特定参数的值"""
        for image_data in self.data.values():
            if image_data and 'measurements' in image_data:
                if param in image_data['measurements']:
                    return image_data['measurements'][param]
        return None

    def generate_report(self) -> str:
        """生成超声报告"""
        report_lines = []

        # 添加报告头部信息
        report_lines.extend([
            "超声心动图报告",
            "=" * 40,
        ])

        # 1. M型+二维+彩色多普勒部分
        chamber_data = None
        for image_type, data in self.data.items():
            if image_type == "心房二维尺寸图" and data and 'measurements' in data:
                chamber_data = data['measurements']
                break

        if chamber_data:
            report_lines.append(self._evaluate_chamber_size(chamber_data))
        else:
            report_lines.append("1.各房室腔大小正常。")

        # 2. 彩色室壁动力学分析
        report_lines.append("\n2. 彩色室壁动力学分析:")
        report_lines.append("左室壁节段性运动未见异常。")

        # 3. 组织多普勒
        report_lines.append("\n3. 组织多普勒:")
        e_velocity = self._get_measurement_value('e_velocity')
        if e_velocity is not None:
            report_lines.append(f"二尖瓣环室间隔位点e' {e_velocity}cm/s")

        # 4. 左心室舒张功能测定
        report_lines.append("\n4. 左心室舒张功能测定:")
        measurements = []

        # 获取所有需要的测量值
        ea = self._get_measurement_value('E/A')
        edt = self._get_measurement_value('EDT')
        ee = self._get_measurement_value('E_Med_E')

        # 按照指定格式组合测量值
        if ea is not None:
            measurements.append(f"E/A {ea}")
        if edt is not None:
            measurements.append(f"EDT {int(edt)}ms")
        if ee is not None:
            measurements.append(f"E/e' {ee}")

        # 如果有测量值，用逗号连接它们
        if measurements:
            report_lines.append("，".join(measurements))

        # 5. 左心室收缩功能测定
        report_lines.append("\n5. 左心室收缩功能测定:")
        edv = self._get_measurement_value('EDV')
        lvef = self._get_measurement_value('LVEF')
        if edv is not None:
            report_lines.append(f"EDV {edv}ml")
        if lvef is not None:
            report_lines.append(f"LVEF {lvef}%（正常值：55%-75%）")

        # 6. 右心室功能测定
        report_lines.append("\n6. 右心室功能测定:")
        tapse_value = self._get_tapse_value()  # 获取原始值
        if tapse_value is not None:
            formatted_tapse = self._format_tapse(tapse_value)  # 只在这里进行一次四舍五入
            report_lines.append(f"TAPSE {formatted_tapse}cm（正常值：＞1.6cm）")

        # 7. 估测肺动脉收缩压
        report_lines.append("\n7. 估测肺动脉收缩压:")
        tr_velocity = self._get_measurement_value('tr_velocity')
        if tr_velocity is not None:
            pressure = self._calculate_pulmonary_pressure(tr_velocity)
            report_lines.append(f"{pressure}mmHg（正常值：＜35mmHg）")
        else:
            report_lines.append("无法计算（缺少必要数据）")

        # 诊断总结
        report_lines.extend([
            "\n诊断总结:",
            "=" * 40
        ])

        diagnoses = []

        ivs = self._get_measurement_value('IVS')
        if ivs and ivs > 11:
            diagnoses.append("室间隔心肌肥厚（基底段）")
        if ea and ea < 1:
            diagnoses.append("左室舒张功能减低")

        if diagnoses:
            report_lines.append("\n".join(diagnoses))
        else:
            report_lines.append("未见明显异常")

        return "\n".join(report_lines)

    @staticmethod
    def img_to_report(current_time, user_login, images):
        report_generator = UltrasoundReport(current_time, user_login)
        report_generator.process_images(images)
        return report_generator.generate_report()
