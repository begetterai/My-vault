"""
Стандарты оформления для Google Docs и Sheets — Ромашка.
Применяется во всех скриптах создания документов.
"""

# ── Google Docs ──────────────────────────────────────────────────
DOCS_MARGIN_TOP    = 56.70   # 20 mm в pt
DOCS_MARGIN_BOTTOM = 56.70
DOCS_MARGIN_LEFT   = 85.05   # 30 mm
DOCS_MARGIN_RIGHT  = 42.52   # 15 mm
DOCS_FONT          = "Times New Roman"
DOCS_SIZE_BODY     = 14
DOCS_SIZE_HEADING  = 18
DOCS_LINE_SPACING  = 150     # 1.5 = 150%
DOCS_INDENT        = 35.43   # 1.25 cm в pt

def apply_doc_styles(session, doc_id):
    """Применить стандартное форматирование к Google Doc."""
    r = session.get(f"https://docs.googleapis.com/v1/documents/{doc_id}")
    doc = r.json()
    body = doc["body"]["content"]
    end_index = body[-1]["endIndex"] - 1

    requests = [
        {
            "updateDocumentStyle": {
                "documentStyle": {
                    "pageSize": {
                        "width":  {"magnitude": 595.28, "unit": "PT"},
                        "height": {"magnitude": 841.89, "unit": "PT"},
                    },
                    "marginTop":    {"magnitude": DOCS_MARGIN_TOP,    "unit": "PT"},
                    "marginBottom": {"magnitude": DOCS_MARGIN_BOTTOM, "unit": "PT"},
                    "marginLeft":   {"magnitude": DOCS_MARGIN_LEFT,   "unit": "PT"},
                    "marginRight":  {"magnitude": DOCS_MARGIN_RIGHT,  "unit": "PT"},
                },
                "fields": "pageSize,marginTop,marginBottom,marginLeft,marginRight"
            }
        },
        {
            "updateTextStyle": {
                "range": {"startIndex": 1, "endIndex": end_index},
                "textStyle": {
                    "weightedFontFamily": {"fontFamily": DOCS_FONT},
                    "fontSize": {"magnitude": DOCS_SIZE_BODY, "unit": "PT"},
                },
                "fields": "weightedFontFamily,fontSize"
            }
        },
        {
            "updateParagraphStyle": {
                "range": {"startIndex": 1, "endIndex": end_index},
                "paragraphStyle": {
                    "alignment": "JUSTIFIED",
                    "lineSpacing": DOCS_LINE_SPACING,
                    "indentFirstLine": {"magnitude": DOCS_INDENT, "unit": "PT"},
                },
                "fields": "alignment,lineSpacing,indentFirstLine"
            }
        },
    ]

    # Headings: bold, 18pt, centered, no indent
    for elem in body:
        if "paragraph" not in elem:
            continue
        para = elem["paragraph"]
        text = "".join(
            e.get("textRun", {}).get("content", "")
            for e in para.get("elements", [])
        ).strip()
        is_heading = (
            text.startswith("БЛОК") or
            text.startswith("SOP —") or
            text.startswith("ONBOARDING") or
            text.startswith("КАССОВАЯ") or
            (text.isupper() and len(text) > 4 and not text.startswith("☐"))
        )
        if not is_heading or text.startswith("━"):
            continue
        s, e = elem["startIndex"], elem["endIndex"]
        requests += [
            {
                "updateTextStyle": {
                    "range": {"startIndex": s, "endIndex": e - 1},
                    "textStyle": {
                        "bold": True,
                        "fontSize": {"magnitude": DOCS_SIZE_HEADING, "unit": "PT"},
                    },
                    "fields": "bold,fontSize"
                }
            },
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": s, "endIndex": e},
                    "paragraphStyle": {
                        "alignment": "CENTER",
                        "indentFirstLine": {"magnitude": 0, "unit": "PT"},
                    },
                    "fields": "alignment,indentFirstLine"
                }
            },
        ]

    r2 = session.post(
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        json={"requests": requests}
    )
    return r2.status_code == 200


# ── Google Sheets ─────────────────────────────────────────────────
SHEETS_FONT         = "Times New Roman"
SHEETS_SIZE_BODY    = 14
SHEETS_SIZE_HEADING = 18
CLR_HEADER = {"red": 0.18, "green": 0.31, "blue": 0.18}   # тёмно-зелёный
CLR_WHITE  = {"red": 1.0,  "green": 1.0,  "blue": 1.0}


def header_format(sheet_id, num_cols):
    """Стандартное форматирование заголовочной строки для Sheets."""
    return [
        # Жирный, 18pt, белый текст, тёмно-зелёный фон, по центру
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0, "endRowIndex": 1,
                    "startColumnIndex": 0, "endColumnIndex": num_cols
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "fontFamily": SHEETS_FONT,
                            "fontSize": SHEETS_SIZE_HEADING,
                            "bold": True,
                            "foregroundColor": CLR_WHITE,
                        },
                        "backgroundColor": CLR_HEADER,
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment,verticalAlignment,wrapStrategy)"
            }
        },
        # Закрепить первую строку
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1}
                },
                "fields": "gridProperties.frozenRowCount"
            }
        },
    ]


def body_format(sheet_id, start_row, end_row, num_cols):
    """Times New Roman 14pt для тела таблицы."""
    return [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row, "endRowIndex": end_row,
                    "startColumnIndex": 0, "endColumnIndex": num_cols
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "fontFamily": SHEETS_FONT,
                            "fontSize": SHEETS_SIZE_BODY,
                        }
                    }
                },
                "fields": "userEnteredFormat.textFormat"
            }
        }
    ]


def autofit_columns(sheet_id, num_cols):
    """Автоподбор ширины столбцов."""
    return [
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": num_cols
                }
            }
        }
    ]
