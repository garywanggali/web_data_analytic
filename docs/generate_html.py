import markdown
import os

# Read Markdown
with open("docs/IEEE_Technical_Report.md", "r", encoding="utf-8") as f:
    text = f.read()

# Convert to HTML
html = markdown.markdown(text, extensions=['fenced_code', 'tables'])

# Add some CSS for IEEE-like styling
styled_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {{
        font-family: "Times New Roman", Times, serif;
        line-height: 1.6;
        max-width: 800px;
        margin: 40px auto;
        padding: 20px;
    }}
    h1 {{
        text-align: center;
        font-size: 24px;
        margin-bottom: 5px;
    }}
    h2 {{
        border-bottom: 1px solid #000;
        padding-bottom: 5px;
        margin-top: 30px;
        font-size: 18px;
        text-transform: uppercase;
    }}
    h3 {{
        font-size: 16px;
        margin-top: 20px;
        font-style: italic;
    }}
    code {{
        background: #f4f4f4;
        padding: 2px 5px;
        font-family: "Courier New", Courier, monospace;
    }}
    pre {{
        background: #f4f4f4;
        padding: 10px;
        overflow-x: auto;
    }}
    table {{
        border-collapse: collapse;
        width: 100%;
        margin: 20px 0;
    }}
    th, td {{
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }}
    th {{
        background-color: #f2f2f2;
    }}
    .center {{
        text-align: center;
    }}
</style>
</head>
<body>
{html}
</body>
</html>
"""

# Write HTML
with open("docs/IEEE_Technical_Report.html", "w", encoding="utf-8") as f:
    f.write(styled_html)

print("HTML report generated at docs/IEEE_Technical_Report.html")
