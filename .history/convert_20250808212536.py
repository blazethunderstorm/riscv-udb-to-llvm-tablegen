#!/usr/bin/env python3
"""
Universal RISC-V UDB to LLVM TableGen Converter
Handles ALL UDB YAML types: instructions, extensions, CSRs, etc.
Usage: python convert.py input.yaml output.td
"""

import yaml
import sys
from pathlib import Path

def extract_encoding_info(format_data):
    """Extract encoding information from UDB format section"""
    encoding = {}
    
    if 'opcodes' in format_data:
        opcodes = format_data['opcodes']
        
        for field in ['funct7', 'funct3', 'funct6', 'funct2', 'opcode']:
            if field in opcodes:
                if isinstance(opcodes[field], dict) and 'value' in opcodes[field]:
                    encoding[field] = opcodes[field]['value']
                elif isinstance(opcodes[field], str):
                    encoding[field] = opcodes[field]
    
    if 'encoding' in format_data:
        enc_data = format_data['encoding']
        if 'match' in enc_data:
            encoding['match'] = enc_data['match']
        if 'variables' in enc_data:
            encoding['variables'] = enc_data['variables']
    
    return encoding

def get_instruction_format(udb_data):
    """Determine instruction format from UDB data"""
    format_data = udb_data.get('format', {})
    
    if '$inherits' in format_data:
        inherit_path = format_data['$inherits'][0] if isinstance(format_data['$inherits'], list) else format_data['$inherits']
        
        if '/R/' in inherit_path or 'R-' in inherit_path:
            return 'R'
        elif '/I/' in inherit_path or 'I-' in inherit_path:
            return 'I'
        elif '/S/' in inherit_path or 'S-' in inherit_path:
            return 'S'
        elif '/B/' in inherit_path or 'B-' in inherit_path:
            return 'B'
        elif '/U/' in inherit_path or 'U-' in inherit_path:
            return 'U'
        elif '/J/' in inherit_path or 'J-' in inherit_path:
            return 'J'
    
    if 'encoding' in udb_data:
        enc = udb_data['encoding']
        if 'match' in enc:
            match_pattern = enc['match']
            if len(match_pattern.replace('-', '')) == 16:
                return 'C'
    
    assembly = udb_data.get('assembly', '')
    if 'vm' in assembly and ('vs1' in assembly or 'vs2' in assembly):
        return 'V'  
    
    return 'R'  

def parse_assembly_operands(assembly_str, inst_for):
    """Parse assembly string and return operand information"""
    if not assembly_str:
        return [], []
    
    parts = [p.strip() for p in assembly_str.split(',')]
    inp = []
    output = []
    
    for part in parts:
        if part.startswith('v') and inst_for == 'V':
            if part == 'vd':
                output.append('VR:$vd')
            elif part.startswith('vs'):
                inp.append(f'VR:${part}')
            elif part == 'vm':
                inp.append('VMaskOp:$vm')
        elif part.startswith('x') or part in ['rd', 'rs1', 'rs2', 'xs1', 'xd']:
            if part in ['xd', 'rd']:
                output.append('GPR:$rd')
            elif part in ['xs1', 'rs1']:
                inp.append('GPR:$rs1')
            elif part in ['xs2', 'rs2']:
                inp.append('GPR:$rs2')
            else:
                inp.append(f'GPR:${part}')
        elif 'imm' in part.lower() or part.isdigit():
            if inst_for == 'I':
                inp.append('simm12:$imm')
            elif inst_for == 'S':
                inp.append('simm12:$imm')
            elif inst_for == 'B':
                inp.append('simm13_lsb0:$imm')
            elif inst_for == 'U':
                inp.append('uimm20:$imm')
            elif inst_for == 'J':
                inp.append('simm21_lsb0:$imm')
            else:
                inp.append('simm12:$imm')
    
    return output, inp

def convert_instruction(udb_data):
    """Convert UDB instruction to TableGen"""
    name = udb_data.get('name', 'unknown')
    long_name = udb_data.get('long_name', name)
    description = udb_data.get('description', '').strip()
    assembly = udb_data.get('assembly', '')
    
    inst_for = get_instruction_format(udb_data)
    format_data = udb_data.get('format', {})
    encoding = extract_encoding_info(format_data)
    
    if 'encoding' in udb_data:
        encoding.update(extract_encoding_info({'encoding': udb_data['encoding']}))
    
    output, inp = parse_assembly_operands(assembly, inst_for)
    
    if not output and not inp:
        if inst_for in ['R', 'I', 'U', 'J']:
            output = ['GPR:$rd']
        if inst_for == 'R':
            inp = ['GPR:$rs1', 'GPR:$rs2']
        elif inst_for == 'I':
            inp = ['GPR:$rs1', 'simm12:$imm']
        elif inst_for in ['S', 'B']:
            inp = ['GPR:$rs1', 'GPR:$rs2', 'simm12:$imm']
            output = []
    
    outputs_str = ', '.join(output)
    inputs_str = ', '.join(inp)
    
    asm_parts = []
    if output:
        asm_parts.extend([f"${op.split(':$')[1]}" for op in output])
    if inp:
        asm_parts.extend([f"${inp.split(':$')[1]}" for inp in inp])
    asm_format = ', '.join(asm_parts)
    
    constraints = []
    
    if 'match' in encoding:
        constraints.append(f'  let EncodingPattern = "{encoding["match"]}";')
    
    for field in ['opcode', 'funct3', 'funct7', 'funct6', 'funct2']:
        if field in encoding:
            value = encoding[field]
            if isinstance(value, str) and value.startswith('0b'):
                constraints.append(f'  let {field.capitalize()} = {value};')
    
    if 'variables' in encoding:
        for var in encoding['variables']:
            var_name = var.get('name', '')
            location = var.get('location', '')
            if var_name and location:
                constraints.append(f'  // Variable {var_name} at bits {location}')
    
    constraint_str = '\n' + '\n'.join(constraints) if constraints else ''
    
    desc_clean = description.replace('\n', ' ').replace('  ', ' ').strip()
    if len(desc_clean) > 100:
        desc_clean = desc_clean[:97] + '...'

    tablegen_name = name.upper().replace('.', '_').replace('-', '_')
    
    return f'''
def {tablegen_name} : RISCVInst<
    (outs {outputs_str}),
    (ins {inputs_str}),
    "{name}", "{asm_format}",
    []> {{
  // {long_name}: {desc_clean}
  let Format = {inst_for}Format;{constraint_str}
}}'''

def convert_csr(udb_data):
    """Convert UDB CSR to TableGen"""
    name = udb_data.get('name', 'unknown')
    long_name = udb_data.get('long_name', name)
    address = udb_data.get('address', '0x000')
    description = udb_data.get('description', '').strip()
    
    desc_clean = description.replace('\n', ' ').replace('  ', ' ').strip()
    if len(desc_clean) > 100:
        desc_clean = desc_clean[:97] + '...'
    
    tablegen_name = name.upper().replace('.', '_').replace('-', '_')
    
    return f'''
def {tablegen_name} : RISCVReg<{address}, "{name}"> {{
  // {long_name}: {desc_clean}
}}'''

def convert_extension(udb_data):
    """Convert UDB extension to TableGen comment block"""
    name = udb_data.get('name', 'unknown')
    long_name = udb_data.get('long_name', name)
    description = udb_data.get('description', '').strip()
    
    desc_clean = description.replace('\n', ' ').replace('  ', ' ').strip()
    
    return f'''
//===----------------------------------------------------------------------===//
// Extension: {name} - {long_name}
// {desc_clean}
//===----------------------------------------------------------------------===//
'''

def process_udb_file(input_file):
    """Process a single UDB YAML file"""
    with open(input_file, 'r') as f:
        try:
            udb_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error parsing {input_file}: {e}")
            return None
    
    if not udb_data or not isinstance(udb_data, dict):
        print(f"Skipping {input_file}: invalid format")
        return None
    
    kind = udb_data.get('kind', 'unknown')
    
    if kind == 'instruction':
        return convert_instruction(udb_data)
    elif kind == 'csr':
        return convert_csr(udb_data)
    elif kind == 'extension':
        return convert_extension(udb_data)
    else:
        print(f"Skipping {input_file}: unknown kind '{kind}'")
        return None

def generate_tablegen_header():
    """Generate TableGen file header"""
    return '''//===-- Generated from RISC-V UDB --------*- tablegen -*-===//
// Auto-generated from RISC-V Unified Database
//===----------------------------------------------------------------------===//

include "RISCVInstrFormats.td"

// Register Classes
def GPR : RegisterClass<"RISCV", [i32], 32, (add
  (sequence "X%u", 0, 31)
)>;

def VR : RegisterClass<"RISCV", [v64i1, v128i1, v256i1, v512i1, v1024i1], 32, (add
  (sequence "V%u", 0, 31)
)>;

// Operand Types
def simm12 : Operand<i32>;
def simm13_lsb0 : Operand<i32>;
def simm21_lsb0 : Operand<i32>;
def uimm20 : Operand<i32>;
def VMaskOp : Operand<i32>;

//===----------------------------------------------------------------------===//
// Generated Content
//===----------------------------------------------------------------------===//
'''

def main():
    if len(sys.argv) < 3:
        print("Usage: python convert.py input.yaml output.td")
        print("   or: python convert.py input_dir/ output_dir/")
        print("\nSupports all UDB YAML types:")
        print("  - Instructions (kind: instruction)")
        print("  - CSRs (kind: csr)")
        print("  - Extensions (kind: extension)")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    if input_path.is_file():
        content = process_udb_file(input_path)
        if content:
            with open(output_path, 'w') as f:
                f.write(generate_tablegen_header())
                f.write(content)
            print(f"Generated {output_path}")
        else:
            print("No content generated")
            
    elif input_path.is_dir():
        output_path.mkdir(exist_ok=True)
        all_content = []

        for yaml_file in sorted(input_path.glob("*.yaml")):
            print(f"Processing {yaml_file.name}...")
            content = process_udb_file(yaml_file)
            if content:
                all_content.append(f"// From {yaml_file.name}")
                all_content.append(content)
        
        if all_content:
            output_file = output_path / "RISCVGenerated.td"
            with open(output_file, 'w') as f:
                f.write(generate_tablegen_header())
                for content in all_content:
                    f.write(content)
                    f.write('\n')
            
            print(f"Generated {output_file} with {len(all_content)//2} items")
        else:
            print("No content found")
    
    else:
        print(f"Error: {input_path} not found")
        sys.exit(1)

if __name__ == '__main__':
    main()