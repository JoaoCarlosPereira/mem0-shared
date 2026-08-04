import sys
import glob

def fix_file(path):
    with open(path, 'r') as f:
        lines = f.readlines()
    
    out_lines = []
    in_ensure_path = False
    
    for line in lines:
        if 'with _ensure_path():' in line:
            in_ensure_path = True
            continue
            
        if in_ensure_path:
            # Check if this line is still indented from with _ensure_path():
            # Usually the imported modules are 12 spaces in, so we remove 4
            if line.startswith('            '):
                out_lines.append(line[4:])
            elif line.startswith('        '):
                # For lines like 'import' that were 12 spaces, or code that is 8 spaces
                # If it's 8 spaces, it might be the start of the next block. 
                # Let's check for method defs or empty lines
                if line.strip() == '' or line.strip().startswith('def ') or line.strip().startswith('class ') or line.strip().startswith('@'):
                    in_ensure_path = False
                    out_lines.append(line)
                else:
                    out_lines.append(line[4:])
            else:
                in_ensure_path = False
                out_lines.append(line)
        else:
            out_lines.append(line)
            
    with open(path, 'w') as f:
        f.writelines(out_lines)

for f in glob.glob('integrations/mem0-plugin/tests/*.py'):
    fix_file(f)
