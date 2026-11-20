import csv
import io
import re
import textwrap
import unicodedata
from datetime import datetime
def csv_data(data):
    if not data: return ""
    f=io.StringIO(); w=csv.DictWriter(f,fieldnames=list(data[0])); w.writeheader(); w.writerows(data); return f.getvalue()

def make_pdf(title, data):
    def clean(value):
        value=unicodedata.normalize("NFKD",str(value if value is not None else "").replace("₹","INR "))
        return "".join(ch if 32<=ord(ch)<127 else " " for ch in value).replace("\\","/")
    lines=["Indaane Cylinder Store - "+clean(title),"Generated "+datetime.now().strftime("%Y-%m-%d %H:%M"),""]
    if not data:
        lines.append("No records found for this report.")
    else:
        fields=list(data[0])
        lines.append("Columns: "+" | ".join(clean(x) for x in fields))
        lines.append("-"*92)
        for record in data:
            entry=" | ".join(clean(k)+": "+clean(record.get(k,"")) for k in fields)
            lines.extend(textwrap.wrap(entry,width=100,subsequent_indent="  ",replace_whitespace=True,drop_whitespace=True) or [""])
            lines.append("")
    pages=[lines[i:i+55] for i in range(0,len(lines),55)] or [[]]
    objects={1:b"<< /Type /Catalog /Pages 2 0 R >>"}
    kids=[]
    for i,page_lines in enumerate(pages):
        page_id=4+i*2; stream_id=page_id+1; kids.append(f"{page_id} 0 R")
        commands=["BT","/F1 9 Tf","42 755 Td","12 TL"]
        commands.append("("+clean(title+" - Page "+str(i+1)+" of "+str(len(pages))).replace("(","\\(").replace(")","\\)")+ ") Tj")
        commands.append("T*")
        for line in page_lines:
            escaped=clean(line).replace("(","\\(").replace(")","\\)")
            commands.append("("+escaped+") Tj"); commands.append("T*")
        commands.append("ET")
        content="\n".join(commands).encode("ascii")
        objects[page_id]=f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode()
        objects[stream_id]=b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"+content+b"\nendstream"
    objects[2]=(f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>").encode()
    objects[3]=b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    output=bytearray(b"%PDF-1.4\n%Indaane\n"); offsets=[0]
    for oid in range(1,max(objects)+1):
        offsets.append(len(output)); output.extend(f"{oid} 0 obj\n".encode()); output.extend(objects[oid]); output.extend(b"\nendobj\n")
    xref=len(output); output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)

