from concurrent.futures import ThreadPoolExecutor

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.platypus import Table, TableStyle

from app.utils.cos import upload_file_to_cos

ultrasound_types = {
    1: "二维心尖", 2: "二维长轴", 3: "多普勒心尖", 4: "多普勒长轴",
    5: "二维心房尺寸图", 6: "左心室M型超声图", 7: "右心室M型超声图",
    8: "左心室组织多普勒图", 9: "右心室组织多普勒图", 10: "频谱图"
}

detection_image_types = {
    1: "二维心尖分割图", 2: "二维长轴分割图", 3: "多普勒心尖反流检测图", 4: "多普勒长轴反流检测图",
    5: "二维心尖热力图", 6: "二维长轴热力图", 7: "多普勒心尖热力图", 8: "多普勒长轴热力图"
}


def generate_pdf_report(case):
    from io import BytesIO
    styles = getSampleStyleSheet()
    # 注册中文字体
    pdfmetrics.registerFont(TTFont('SimSun', 'font/hei.ttf'))  # 根据系统路径修改
    styles.add(ParagraphStyle(name='Chinese', parent=styles['Normal'], fontName='SimSun'))
    styles.add(ParagraphStyle(name='MyTitle', fontName='SimSun', fontSize=20, alignment=TA_CENTER, spaceAfter=20))
    styles.add(
        ParagraphStyle(name='LargeChinese', parent=styles['Normal'], fontName='SimSun', fontSize=14, spaceBefore=12,
                       spaceAfter=12))
    styles.add(
        ParagraphStyle(name='SectionTitle', parent=styles['Chinese'], fontSize=16, spaceBefore=12, spaceAfter=12))

    def load_image(path):
        try:
            return RLImage(path, width=90, height=67)
        except Exception:
            return Paragraph("(图像加载失败)", styles["Chinese"])

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    content = []

    def gender_to_str(g):
        return "男" if g == 1 else "女"

    content.append(Paragraph("心脏超声检测报告", styles["MyTitle"]))
    content.append(Paragraph("基本信息：", styles["SectionTitle"]))
    content.append(Paragraph(f"患者姓名：{case.name}", styles["Chinese"]))
    content.append(Paragraph(f"性别：{gender_to_str(case.gender)}", styles["Chinese"]))
    content.append(Paragraph(f"年龄：{case.age}", styles["Chinese"]))
    content.append(Paragraph(f"备注：{case.notes or '无'}", styles["Chinese"]))
    content.append(Paragraph(f"就诊时间：{case.created_at.strftime('%Y-%m-%d %H:%M:%S')}", styles["Chinese"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("超声图像列表：", styles["SectionTitle"]))
    # 超声图像表格
    image_cells = []
    image_paths = [(img.file_path, ultrasound_types.get(img.image_type, f"类型{img.image_type}")) for img in
                   case.ultrasound_images]
    with ThreadPoolExecutor(max_workers=8) as executor:
        images = list(executor.map(lambda p: (load_image(p[0]), p[1]), image_paths))
    for image, label in images:
        cell = Table(
            [
                [image],
                [Paragraph(label, ParagraphStyle(name='CenterChinese', parent=styles['Chinese'], alignment=TA_CENTER))]
            ],
            colWidths=[120],
            style=TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ])
        )
        image_cells.append(cell)

    rows = []
    row = []
    for i, cell in enumerate(image_cells, 1):
        row.append(cell)
        if i % 4 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    for r in rows:
        t = Table([r], colWidths=[120] * len(r))
        t.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        content.append(t)
        content.append(Spacer(1, 12))

    for result in case.detection_results:
        conclusion_text = result.conclusion.replace('\n', '<br/>')
        description_text = result.description.replace('\n', '<br/>')
        content.append(Spacer(1, 6))
        content.append(Paragraph("结论：", styles["SectionTitle"]))
        content.append(Paragraph(f"<br/>{conclusion_text}", styles["Chinese"]))
        content.append(Spacer(1, 6))
        content.append(Paragraph("描述：", styles["SectionTitle"]))
        content.append(Paragraph(f"<br/>{description_text}", styles["Chinese"]))
        content.append(Spacer(1, 12))
        content.append(Paragraph(f"模型置信度：{result.confidence * 100:.2f}%", styles["Chinese"]))
        content.append(Paragraph(f"完成时间：{result.result_time}", styles["Chinese"]))

        content.append(Paragraph("诊断图片：", styles["SectionTitle"]))
        detection_cells = []
        image_paths = [(dimg.file_path, detection_image_types.get(dimg.image_type, f"类型{dimg.image_type}")) for dimg
                       in result.detection_images]
        with ThreadPoolExecutor(max_workers=8) as executor:
            images = list(executor.map(lambda p: (load_image(p[0]), p[1]), image_paths))
        for image, label in images:
            cell = Table(
                [
                    [image],
                    [Paragraph(label,
                               ParagraphStyle(name='CenterChinese', parent=styles['Chinese'], alignment=TA_CENTER))]
                ],
                colWidths=[120],
                style=TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ])
            )
            detection_cells.append(cell)

        rows = []
        row = []
        for i, cell in enumerate(detection_cells, 1):
            row.append(cell)
            if i % 4 == 0:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

        for r in rows:
            t = Table([r], colWidths=[120] * len(r))
            t.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            content.append(t)
            content.append(Spacer(1, 12))

    doc.build(content)

    # 上传报告到 COS
    buffer.seek(0)

    filename = f"report_{case.id}.pdf"
    cos_url = upload_file_to_cos(buffer, filename, content_type="application/pdf", path_prefix="reports")

    return cos_url
