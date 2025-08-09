//===-- Generated from RISC-V UDB --------*- tablegen -*-===//
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

def ADDW : RISCVInst<
    (outs GPR:$rd),
    (ins GPR:$rs1, GPR:$rs2),
    "addw", "$rd, $rs1, $rs2",
    []> {
  // Add word: Add the 32-bit values in xs1 to xs2, and store the sign-extended result in xd. Any overflow is th...
  let Format = RFormat;
  let EncodingPattern = "0000000----------000-----0111011";
  // Variable xs2 at bits 24-20
  // Variable xs1 at bits 19-15
  // Variable xd at bits 11-7
}