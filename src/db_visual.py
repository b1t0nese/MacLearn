import sqlite3
import os


def generate_html_schema(db_path, output_file=None):
    if not output_file:
        output_file = os.path.join(os.path.dirname(db_path), "database_schema.html")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Database Schema</title>
    <style>
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            margin: 40px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .schema-container {
            display: flex;
            flex-wrap: wrap;
            gap: 30px;
            justify-content: center;
            position: relative;
        }
        .table-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            width: 320px;
            min-height: 200px;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            position: absolute;
            z-index: 1;
            cursor: move;
        }
        .table-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(0,0,0,0.2);
        }
        .table-card.dragging {
            cursor: grabbing;
            opacity: 0.9;
        }
        .table-header {
            background: linear-gradient(135deg, #007acc, #00a8ff);
            color: white;
            padding: 15px;
            border-radius: 12px 12px 0 0;
            font-weight: bold;
            font-size: 1.1em;
            cursor: grab;
            user-select: none;
        }
        .table-header:active {
            cursor: grabbing;
        }
        .table-content {
            padding: 15px;
        }
        .column {
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .column:last-child {
            border-bottom: none;
        }
        .column-name {
            font-weight: 600;
            color: #333;
        }
        .column-type {
            color: #666;
            font-size: 0.9em;
        }
        .pk {
            background: #fff9e6;
            margin: 0 -15px;
            padding: 8px 15px;
            border-left: 3px solid #ffc107;
        }
        .pk-badge {
            background: #ffc107;
            color: #333;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.7em;
            font-weight: bold;
            margin-left: 8px;
        }
        .relationship-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
        }
        .relationship-line {
            stroke: #ff6b35;
            stroke-width: 4;
            marker-end: url(#arrowhead);
            opacity: 0.9;
            transition: all 0.3s ease;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        }
        .relationship-line:hover {
            opacity: 1;
            stroke-width: 5;
            stroke: #e55a2b;
        }
        .relationship-label {
            fill: white;
            font-size: 16px;
            font-weight: bold;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
            pointer-events: none;
        }
        .relationship-label-bg {
            fill: #ff6b35;
            rx: 8px;
            ry: 8px;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        }
        .not-null {
            color: #e74c3c;
            font-size: 0.8em;
            margin-left: 5px;
        }
        .default-value {
            color: #27ae60;
            font-size: 0.8em;
            font-style: italic;
            margin-left: 5px;
        }
        .table-stats {
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 0 0 12px 12px;
            font-size: 0.8em;
            color: #666;
            display: flex;
            justify-content: space-between;
        }
        .tooltip {
            position: fixed;
            background: #333;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            z-index: 1000;
            pointer-events: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Структура базы данных</h1>
        </div>

        <div class="schema-container" id="schemaContainer">
'''

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cur.fetchall()

    table_data = {}
    relationships = []

    for i, (table_name,) in enumerate(tables):
        row = i // 3
        col = i % 3
        left = col * 350 + 50
        top = row * 300 + 50

        table_data[table_name] = {
            'id': f'table_{table_name}',
            'left': left,
            'top': top,
            'columns': []
        }

        cur.execute(f"PRAGMA table_info({table_name});")
        columns = cur.fetchall()

        columns_html = ""
        for col in columns:
            col_id, col_name, col_type, not_null, default_val, pk = col

            attributes = []
            if pk: 
                attributes.append('<span class="pk-badge">PK</span>')
            if not_null: 
                attributes.append('<span class="not-null">NOT NULL</span>')
            if default_val: 
                attributes.append(f'<span class="default-value">DEFAULT {default_val}</span>')

            attr_html = " ".join(attributes)
            pk_class = "pk" if pk else ""

            columns_html += f"""
        <div class="column {pk_class}">
            <span class="column-name">{col_name}</span>
            <div>
                <span class="column-type">{col_type}</span>
                {attr_html}
            </div>
        </div>
        """

            table_data[table_name]['columns'].append({
                'name': col_name,
                'type': col_type,
                'pk': pk
            })

        cur.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cur.fetchone()[0]
        
        html_content += f"""
    <div class="table-card" id="table_{table_name}" style="left: {left}px; top: {top}px;">
        <div class="table-header">
            📊 {table_name}
        </div>
        <div class="table-content">
            {columns_html}
        </div>
        <div class="table-stats">
            <span>Столбцов: {len(columns)}</span>
            <span>Записей: {count}</span>
        </div>
    </div>
    """

        cur.execute(f"PRAGMA foreign_key_list({table_name});")
        foreign_keys = cur.fetchall()
        
        for fk in foreign_keys:
            _, _, ref_table, from_col, to_col, *_ = fk
            relationships.append({
                'from_table': table_name,
                'from_column': from_col,
                'to_table': ref_table,
                'to_column': to_col
            })

    html_content += """
        </div>
        
        <svg class="relationship-container" id="relationshipSVG"></svg>
    </div>

    <script>
        function drawRelationships() {
            const svg = document.getElementById('relationshipSVG');
            const relationships = """ + str(relationships).replace("'", '"') + """;

            svg.innerHTML = `
                <defs>
                    <marker id="arrowhead" markerWidth="12" markerHeight="8" 
                            refX="11" refY="4" orient="auto">
                        <polygon points="0 0, 12 4, 0 8" fill="#ff6b35"/>
                    </marker>
                </defs>
            `;

            relationships.forEach(rel => {
                const fromTable = document.getElementById('table_' + rel.from_table);
                const toTable = document.getElementById('table_' + rel.to_table);

                if (fromTable && toTable) {
                    const fromRect = fromTable.getBoundingClientRect();
                    const toRect = toTable.getBoundingClientRect();
                    const svgRect = svg.getBoundingClientRect();

                    const fromX = fromRect.left + fromRect.width - svgRect.left;
                    const fromY = fromRect.top + fromRect.height / 2 - svgRect.top;
                    const toX = toRect.left - svgRect.left;
                    const toY = toRect.top + toRect.height / 2 - svgRect.top;

                    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                    line.setAttribute("x1", fromX);
                    line.setAttribute("y1", fromY);
                    line.setAttribute("x2", toX);
                    line.setAttribute("y2", toY);
                    line.setAttribute("class", "relationship-line");
                    line.setAttribute("data-relationship", 
                        `${rel.from_table}.${rel.from_column} → ${rel.to_table}.${rel.to_column}`);

                    const textX = (fromX + toX) / 2;
                    const textY = (fromY + toY) / 2 - 8;

                    // Сначала создаем текст чтобы измерить его ширину
                    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                    text.setAttribute("x", textX);
                    text.setAttribute("y", textY);
                    text.setAttribute("text-anchor", "middle");
                    text.setAttribute("class", "relationship-label");
                    text.setAttribute("dominant-baseline", "middle");
                    text.textContent = `${rel.from_column}→${rel.to_column}`;
                    
                    // Временно добавляем текст чтобы измерить его размеры
                    svg.appendChild(text);
                    const textBBox = text.getBBox();
                    
                    // Теперь создаем фон с точными размерами текста
                    const textBg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
                    const padding = 12; // Отступ вокруг текста
                    textBg.setAttribute("x", textBBox.x - padding/2);
                    textBg.setAttribute("y", textBBox.y - padding/4);
                    textBg.setAttribute("width", textBBox.width + padding);
                    textBg.setAttribute("height", textBBox.height + padding/2);
                    textBg.setAttribute("class", "relationship-label-bg");
                    textBg.setAttribute("rx", "8");
                    textBg.setAttribute("ry", "8");

                    // Добавляем элементы в правильном порядке (сначала фон, потом текст, потом линия)
                    svg.appendChild(textBg);
                    svg.appendChild(text);
                    svg.appendChild(line);

                    line.addEventListener('mouseenter', function(e) {
                        const tooltip = document.createElement('div');
                        tooltip.className = 'tooltip';
                        tooltip.textContent = this.getAttribute('data-relationship');
                        tooltip.style.cssText = `
                            position: fixed;
                            background: #333;
                            color: white;
                            padding: 8px 12px;
                            border-radius: 6px;
                            font-size: 12px;
                            z-index: 1000;
                            left: ${e.clientX + 15}px;
                            top: ${e.clientY + 15}px;
                        `;
                        document.body.appendChild(tooltip);
                    });
                    
                    line.addEventListener('mouseleave', function() {
                        const tooltips = document.querySelectorAll('.tooltip');
                        tooltips.forEach(t => t.remove());
                    });
                }
            });
        }

        window.addEventListener('load', drawRelationships);
        window.addEventListener('resize', drawRelationships);

        let draggedTable = null;
        let startX, startY, initialLeft, initialTop;

        document.querySelectorAll('.table-card').forEach(table => {
            const header = table.querySelector('.table-header');
            header.addEventListener('mousedown', function(e) {
                draggedTable = table;
                startX = e.clientX;
                startY = e.clientY;
                const style = window.getComputedStyle(table);
                initialLeft = parseInt(style.left);
                initialTop = parseInt(style.top);
                table.classList.add('dragging');
                table.style.zIndex = '1000';
                e.preventDefault();
            });
        });

        document.addEventListener('mousemove', function(e) {
            if (draggedTable) {
                const deltaX = e.clientX - startX;
                const deltaY = e.clientY - startY;
                draggedTable.style.left = (initialLeft + deltaX) + 'px';
                draggedTable.style.top = (initialTop + deltaY) + 'px';
                drawRelationships();
            }
        });

        document.addEventListener('mouseup', function() {
            if (draggedTable) {
                draggedTable.classList.remove('dragging');
                draggedTable.style.zIndex = '1';
                draggedTable = null;
            }
        });
    </script>
</body>
</html>"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    conn.close()
    print(f"🎉 Интерактивная HTML-схема сохранена как: {output_file}")
    print("✨ Возможности:")
    print("   • Перетаскивайте карточки таблиц за заголовок")
    print("   • Наводите на стрелки для просмотра связей")
    print("   • Автоматическое обновление связей при перемещении")


generate_html_schema(input("Введите путь к БД: "))