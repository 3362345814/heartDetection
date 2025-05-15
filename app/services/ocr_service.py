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

from app.core.config import settings


class XunfeiOCR:
    def recognize_from_base64(self, image_base64: str, max_retries=3) -> Dict:
        for attempt in range(max_retries):
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
                for page in text_data.get('pages', []):
                    for line in page.get('lines', []):
                        for word in line.get('words', []):
                            if 'content' in word:
                                recognized_text.append(word['content'])

                if not recognized_text:
                    raise Exception("未能识别到任何文本")

                return self._parse_ultrasound_data(' '.join(recognized_text))

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                raise Exception(f"OCR识别失败: {str(e)}")

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
        """解析超声图像文本数据，支持中英文参数"""
        data = {
            'raw_text': text,
            'measurements': {},
            'parameters': {}
        }

        # 心房二维尺寸图处理：支持英文"Dist"和中文"距离"
        distances = []
        # 匹配英文格式
        dist_matches = re.finditer(r'Dist\s*([\d.]+)\s*cm', text)
        for match in dist_matches:
            distances.append(float(match.group(1)))

        # 如果没有找到英文格式，尝试匹配中文格式
        if not distances:
            dist_matches = re.finditer(r'距\s*离\s*([\d.]+)\s*(?:cm|厘米)', text)
            for match in dist_matches:
                distances.append(float(match.group(1)))

        if len(distances) >= 4:
            data['measurements'].update({
                'RA_length': distances[0],
                'RA_short': distances[1],
                'LA_length': distances[2],
                'LA_short': distances[3]
            })
        elif len(distances) == 1 and "2D/MM" in text:
            # 如果只有1个距离值且在M型图中，认为是TAPSE测量
            data['measurements']['TAPSE_dist'] = float(distances[0])

        # 左心室M型超声图参数处理
        if any(x in text for x in ["EDV", "ESV", "EF", "舒张末容积", "收缩末容积", "射血分数"]):
            parameters_to_find = {
                'EDV': r'(?:EDV[^0-9]*|舒张末容积[^0-9]*)([\d.]+)(?:\s*ml|\s*毫升)?',
                'ESV': r'(?:ESV[^0-9]*|收缩末容积[^0-9]*)([\d.]+)(?:\s*ml|\s*毫升)?',
                'LVEF': r'(?:LVEF|EF|射血分数)[^0-9]*([\d.]+)(?:\s*%)?',
                'FS': r'(?:FS|缩短分数)[^0-9]*([\d.]+)(?:\s*%)?',
                'IVS': r'(?:IVS|室间隔)[^0-9]*([\d.]+)(?:\s*mm|\s*毫米)?'
            }

            for param, pattern in parameters_to_find.items():
                match = re.search(pattern, text)
                if match:
                    try:
                        data['measurements'][param] = float(match.group(1))
                    except ValueError:
                        continue

        # 左心室组织多普勒图参数处理
        if any(x in text for x in ['Med E', 'E Med E', '内侧E速度', 'E/内侧E']):
            # 匹配e_velocity
            e_vel_patterns = [
                r'(?:Med\s*E|E\s*Med)\s*(?:Vel\s*)?([\d.]+)(?:\s*cm/?s)?',
                r'内侧E速度\s*([\d.]+)(?:\s*cm/s)?',
                r'中隔E速度\s*([\d.]+)(?:\s*cm/s)?'
            ]

            for pattern in e_vel_patterns:
                match = re.search(pattern, text)
                if match:
                    data['measurements']['e_velocity'] = float(match.group(1))
                    break

            # 匹配E/Med E
            e_med_e_patterns = [
                r'(?:E/Med\s*E|E\s*Med\s*E|E/E)\s*([\d.]+)',
                r'E/内侧E\s*([\d.]+)',
                r'E／内侧E\s*([\d.]+)'
            ]

            for pattern in e_med_e_patterns:
                match = re.search(pattern, text)
                if match:
                    data['measurements']['E_Med_E'] = float(match.group(1))
                    break

        # 左心室频谱多普勒图参数处理
        if any(x in text for x in ['Decel Time', 'E/A', 'EJA', 'MV减速时间', 'E／A']):
            # 匹配EDT (Decel Time)
            edt_patterns = [
                r'(?:MV\s+)?Decel Time\s*([\d.]+)(?:\s*ms)?',
                r'减速时间.*?(\d+)\s*ms',
                r'(?:.*?)(\d+)\s*ms'  # 最后尝试匹配任何ms前的数字
            ]

            for pattern in edt_patterns:
                edt_match = re.search(pattern, text)
                if edt_match:
                    data['measurements']['EDT'] = float(edt_match.group(1))
                    break

            # 匹配E/A值
            ea_patterns = [
                r'(?:MV\s+)?E/A\s*([\d.]+)',
                r'EJA\s*([\d.]+)',
                r'E／A\s*([\d.]+)'
            ]

            for pattern in ea_patterns:
                ea_match = re.search(pattern, text)
                if ea_match:
                    data['measurements']['E/A'] = float(ea_match.group(1))
                    break

        # 右心室组织多普勒图参数处理
        if any(x in text for x in ['Vel', 'PG', '速度', '压力梯度']):
            # 匹配tr_velocity
            vel_patterns = [
                r'Vel\s*([\d.]+)(?:\s*cm/s)?',
                r'速度\s*([\d.]+)(?:\s*cm/s)?'
            ]

            for pattern in vel_patterns:
                tr_vel_match = re.search(pattern, text)
                if tr_vel_match and ('速度' in text and '压力梯度' in text or 'PG' in text):
                    data['measurements']['tr_velocity'] = float(tr_vel_match.group(1))
                    break

            # 匹配压力梯度
            pg_patterns = [
                r'PG\s*([\d.]+)(?:\s*mmHg)?',
                r'压力梯度\s*([\d.]+)(?:\s*mmHg)?'
            ]

            for pattern in pg_patterns:
                pg_match = re.search(pattern, text)
                if pg_match:
                    data['measurements']['pg'] = float(pg_match.group(1))
                    break

        return data

    def recognize(self, image_path: str, max_retries=3) -> Dict:
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


class UltrasoundReport:
    def __init__(self, image_map: Dict[int, str]):
        self.type_name_map = {
            5: "心房二维尺寸图",
            6: "左心室M型超声图",
            7: "右心室M型超声图",
            8: "左心室组织多普勒图",
            9: "右心室组织多普勒图",
            10: "左心室频谱多普勒图"
        }
        self.image_map = image_map
        self.data = {}
        self.ocr = XunfeiOCR(
            app_id=settings.OCR_APP_ID,
            api_key=settings.OCR_API_KEY,
            api_secret=settings.OCR_API_SECRET
        )

    def process_images(self):
        """处理所有超声图像（通过URL下载并识别）"""
        for type_id, image_url in self.image_map.items():
            image_type = self.type_name_map.get(type_id)
            if not image_type:
                continue
            try:
                response = requests.get(image_url)
                image_base64 = base64.b64encode(response.content).decode('utf-8')
                result = self.ocr.recognize_from_base64(image_base64)
                self.data[image_type] = result
            except Exception as e:
                print(f"{image_type} 识别失败: {e}")

    def _get_tapse_value(self) -> Optional[float]:
        """
        获取TAPSE值，专门从右心室M型超声图中获取
        返回：四舍五入到整数位的TAPSE值，如果没有找到则返回None
        """
        if "右心室M型超声图" in self.data and self.data["右心室M型超声图"]:
            measurements = self.data["右心室M型超声图"].get('measurements', {})
            if 'TAPSE_dist' in measurements:
                raw_value = measurements['TAPSE_dist']
                # 四舍五入到整数位
                return round(raw_value * 10) / 10
        return None

    def _format_tapse(self, value: float) -> float:
        """格式化TAPSE值，进行四舍五入到整数位"""
        if value is None:
            return None
        # 四舍五入到整数位
        return round(value)

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
    def report(image_map: Dict[int, str]):
        report_generator = UltrasoundReport(image_map)
        report_generator.process_images()
        return report_generator.generate_report()
