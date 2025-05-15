import os
import re
import sys
import yaml
from pathlib import Path
from datetime import datetime
from html2text import HTML2Text

def html_to_markdown(html: str) -> str:
    h = HTML2Text()
    h.ignore_links = False
    h.body_width = 0
    return h.handle(html)

import re

def parse_mt_export(file_path):
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    entries = content.split("\n--------\n")
    parsed = []

    for entry in entries:
        fields = {}
        bodies = {}
        lines = entry.strip().split("\n")
        buffer_key = None
        buffer_val = []

        for line in lines:
            # 末尾のセパレータを無視
            if line.strip() == "-----" and buffer_key is None:
                continue

            if re.match(r'^[A-Z ]+:$', line):
                if buffer_key:
                    bodies[buffer_key] = "\n".join(buffer_val).strip()
                    buffer_val = []
                buffer_key = line.rstrip(":")
            elif re.match(r'^[A-Z ]+:', line):
                if buffer_key:
                    bodies[buffer_key] = "\n".join(buffer_val).strip()
                    buffer_key = None
                    buffer_val = []
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()

                # CATEGORY が複数行あった場合リストとして保持
                if key == "CATEGORY":
                    if "CATEGORY" in fields:
                        if isinstance(fields["CATEGORY"], list):
                            fields["CATEGORY"].append(val)
                        else:
                            fields["CATEGORY"] = [fields["CATEGORY"], val]
                    else:
                        fields["CATEGORY"] = [val]
                else:
                    fields[key] = val
            elif buffer_key:
                # セクション中の中間の ----- は無視
                if line.strip() == "-----":
                    continue
                buffer_val.append(line)

        if buffer_key:
            bodies[buffer_key] = "\n".join(buffer_val).strip()

        parsed.append((fields, bodies))

    return parsed

def write_markdown_and_redirects(parsed, section, output_dir, redirect_file_path):
    os.makedirs(output_dir, exist_ok=True)
    redirects = []

    for fields, bodies in parsed:
        title = fields.get("TITLE", "No Title")
        basename = fields.get("BASENAME", re.sub(r'\W+', '-', title.lower()))
        date_str = fields.get("DATE", "2000-01-01 00:00:00")
        status = fields.get("STATUS", "Publish")
        draft = (status.lower() != "publish")

        # 日付から年月取得
        try:
            dt = datetime.strptime(date_str, "%m/%d/%Y %I:%M:%S %p")
        except ValueError:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        yyyy = dt.strftime("%Y")
        mm = dt.strftime("%m")

        # Markdownファイル保存パス
        subdir = Path(output_dir) / yyyy / mm / "posts"
        subdir.mkdir(parents=True, exist_ok=True)
        md_path = subdir / f"{basename}.md"

        # フロントマター作成
        aliases = [f"/blog/{section}/{basename}.html"]
        frontmatter = {
            "title": title,
            "date": dt.isoformat(),
            "draft": draft,
            "tags": fields.get("TAGS").split(",") if "TAGS" in fields else [],
            "categories": fields.get("CATEGORY") if "CATEGORY" in fields else [],
            "aliases": aliases
        }

        body_md = html_to_markdown(bodies.get("BODY", ""))
        extended_md = html_to_markdown(bodies.get("EXTENDED BODY", ""))
        content = body_md
        if extended_md:
            content += "\n" + extended_md

        # Markdown書き込み
        with open(md_path, "w", encoding="utf-8") as f:
            f.write('---\n')
            for key, value in frontmatter.items():
                if isinstance(value, list):
                    quoted_items = []
                    for v in value:
                        s = str(v).strip()          # まず文字列に変換し前後の空白を除去
                        s = s.strip('"')            # 先頭と末尾のダブルクォートを削除
                        quoted = f'"{s}"'           # 最後にダブルクォートで囲む
                        quoted_items.append(quoted)
                    result = ', '.join(quoted_items)
                    f.write(f'{key}: [{result}]\n')
                elif isinstance(value, bool):
                    f.write(f'{key}: {"true" if value else "false"}\n')
                else:
                    escaped_value = str(value).replace('"', '\\"')
                    f.write(f'{key}: "{escaped_value}"\n')
            f.write("---\n\n")
            f.write(content.strip())

        # nginx リダイレクトルール
        redirects.append(f'rewrite ^/blog/{section}/{yyyy}/{mm}/{basename}\\.html$ https://example.com/{section}/{yyyy}/{mm}/posts/{basename}/ permanent;')

    # リダイレクトファイル書き込み
    with open(redirect_file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(redirects))
        f.write("\n")

def main():
    if len(sys.argv) != 4:
        print("Usage: python mt_export_to_hugo.py <mt_export.txt> <section> <output_folder>")
        return

    input_file = sys.argv[1]
    section = sys.argv[2]
    output_dir = f"content/{section}"
    redirect_file = "nginx_redirects.conf"

    parsed = parse_mt_export(input_file)
    write_markdown_and_redirects(parsed, section, output_dir, redirect_file)
    print(f"✅ Done. Markdown files written to '{output_dir}', nginx config to '{redirect_file}'.")

if __name__ == "__main__":
    main()