from enum import Enum, auto
import re


class IRK(Enum):
    GetLocal     = auto()
    PushLabel    = auto()
    PushInt      = auto()
    AllocTemps   = auto()
    FreeTemps    = auto()
    StoreTemp    = auto()
    SetArgTemp   = auto()
    Call         = auto()
    PopCall      = auto()
    Plus         = auto()
    OpAdd        = auto()
    OpSub        = auto()
    OpMul        = auto()
    OpDiv        = auto()
    OpMod        = auto()
    OpEq         = auto()
    OpNotEq      = auto()
    OpLess       = auto()
    OpLessEq     = auto()
    OpGreater    = auto()
    OpGreaterEq  = auto()
    PopReturn    = auto()
    ReturnVoid   = auto()
    SetLocal     = auto()
    NewProc      = auto()
    SetLocalArg  = auto()
    CloseProc    = auto()
    GotoTopFalse = auto()
    GotoTopTrue  = auto()
    GotoFalse    = auto()
    Goto         = auto()
    Label        = auto()
    PtrRead      = auto()
    PtrWrite     = auto()
    BitNot       = auto()
    LogicNot     = auto()
    LogicAnd     = auto()
    LogicOr      = auto()
    InlineAsm    = auto()
    LazyIdent    = auto()
    CallLazyIdent = auto()

structs = [
    (IRK.AllocTemps, ['src_loc', 'n']),
    (IRK.Call, ['src_loc', 'label', 'varargs']),
    (IRK.CallLazyIdent, ['src_loc', 'ident', 'nargs']),
    (IRK.CloseProc, ['src_loc', 'name']),
    (IRK.FreeTemps, ['src_loc', 'n']),
    (IRK.GetLocal, ['src_loc', 'local', 'n']),
    (IRK.Goto, ['src_loc', 'label']),
    (IRK.GotoFalse, ['src_loc', 'label']),
    (IRK.GotoTopFalse, ['src_loc', 'label']),
    (IRK.GotoTopTrue, ['src_loc', 'label']),
    (IRK.InlineAsm, ['src_loc', 'name', 'asm']),
    (IRK.Label, ['src_loc', 'label']),
    (IRK.LogicNot, ['src_loc']),
    (IRK.NewProc, ['src_loc', 'src_name', 'name', 'params', 'locals']),
    (IRK.OpAdd, ['src_loc']),
    (IRK.OpDiv, ['src_loc']),
    (IRK.OpEq, ['src_loc']),
    (IRK.OpGreater, ['src_loc']),
    (IRK.OpGreaterEq, ['src_loc']),
    (IRK.OpLess, ['src_loc']),
    (IRK.OpLessEq, ['src_loc']),
    (IRK.OpMod, ['src_loc']),
    (IRK.OpMul, ['src_loc']),
    (IRK.OpNotEq, ['src_loc']),
    (IRK.OpSub, ['src_loc']),
    (IRK.PopCall, ['src_loc']),
    (IRK.PopReturn, ['src_loc']),
    (IRK.PtrRead, ['src_loc', 'size']),
    (IRK.PtrWrite, ['src_loc', 'size']),
    (IRK.PushInt, ['src_loc', 'value']),
    (IRK.PushLabel, ['src_loc', 'label']),
    (IRK.ReturnVoid, ['src_loc']),
    (IRK.SetArgTemp, ['src_loc', 'n']),
    (IRK.SetLocal, ['src_loc', 'local', 'n']),
    (IRK.SetLocalArg, ['src_loc', 'local', 'arg']),
    (IRK.StoreTemp, ['src_loc', 'n']),
]

def snake_case(name):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

if False:
    for k, v in structs:
        k_name = str(k).split('.')[1]
        fn_name = f"make_ir_{snake_case(k_name)}"
        args = ", ".join(v)
        print(f"proc {fn_name} {args} in")
        print(f"    var self = malloc(sizeof_TIR_INSTR);")
        print(f"    u64!(self + TIR_INSTR_kind, IRK_{k_name});")
        for field in v:
            print(f"    u64!(self + TIR_INSTR_{field}, {field});")
        print(f"    return self;")
        print(f"end")

if False:
    for k, v in structs:
        k_name = str(k).split('.')[1]
        print(f"proc print_ir_{snake_case(k_name)} self in")
        for field in v:
            print(f"    print(u64@(self + TIR_INSTR_{field}));")
        print(f"end")


if False:
    ir_instr = [
        ("TIR_INSTR_kind"    , "kind"),
        ("TIR_INSTR_src_loc" , "src_loc"),
        ("TIR_INSTR_name"    , "name"),
        ("TIR_INSTR_ident"   , "ident"),
        ("TIR_INSTR_local"   , "local"),
        ("TIR_INSTR_label"   , "label"),
        ("TIR_INSTR_n"       , "n"),
        ("TIR_INSTR_nargs"   , "nargs"),
        ("TIR_INSTR_params"  , "params"),
        ("TIR_INSTR_size"    , "size"),
        ("TIR_INSTR_value"   , "value"),
        ("TIR_INSTR_varargs" , "varargs"),
        ("TIR_INSTR_asm"     , "asm"),
        ("TIR_INSTR_arg"     , "arg"),
        ("TIR_INSTR_src_name", "src_name"),
        ("TIR_INSTR_locals"  , "locals"),
    ]
    for k, v in ir_instr:
        print(f"proc ir_instr_{v} self in return u64@(self + {k}); end")


def struct_gen(struct_name, fields):
    prefix = f"T{struct_name.upper()}";
    i = 0
    for f in fields:
        print(f"const {prefix}_{f} = {i*8};")
        i = i + 1;
    print(f"const sizeof_{prefix} = {i*8};")
    print()
    args = ", ".join(fields)
    print(f"proc make_{struct_name} {args} in")
    print(f"    var self = malloc(sizeof_{prefix});")
    for f in fields:
        print(f"    u64!(self + {prefix}_{f}, {f});")
    print(f"    return self;")
    print(f"end")
    print()
    for f in fields:
        print(f"proc {struct_name}_{f} self in return u64@(self + {prefix}_{f}); end")
    
if True:
    struct_gen("field", ["name", "offset", "type"])

if False:
    struct_gen("proc_info", ["label", "params", "varargs"])

if False:
    printers = {
        "label": "%s",
        "n": "%d",
        "varargs": "%d",
        "ident": "%s",
        "nargs": "%d",
        "name": "%s",
        "local": "%s",
        "src_name": "%s",
        "params": "TODO(params) %p",
        "locals": "TODO(locals) %p",
        "size": "%d",
        "value": "%d",
        "arg": "%d",
        }
    ir_structs = [
        (IRK.AllocTemps, ["n"]),
        (IRK.Call, ["label", "varargs"]),
        (IRK.CallLazyIdent, ["ident", "nargs"]),
        (IRK.CloseProc, ["name"]),
        (IRK.FreeTemps, ["n"]),
        (IRK.GetLocal, ["local", "n"]),
        (IRK.Goto, ["label"]),
        (IRK.GotoFalse, ["label"]),
        (IRK.GotoTopFalse, ["label"]),
        (IRK.GotoTopTrue, ["label"]),
        (IRK.InlineAsm, ["name"]),
        (IRK.Label, ["label"]),
        (IRK.LogicNot, []),
        (IRK.NewProc, ["src_name", "name", "params", "locals"]),
        (IRK.OpAdd, []),
        (IRK.OpDiv, []),
        (IRK.OpEq, []),
        (IRK.OpGreater, []),
        (IRK.OpGreaterEq, []),
        (IRK.OpLess, []),
        (IRK.OpLessEq, []),
        (IRK.OpMod, []),
        (IRK.OpMul, []),
        (IRK.OpNotEq, []),
        (IRK.OpSub, []),
        (IRK.PopCall, []),
        (IRK.PopReturn, []),
        (IRK.PtrRead, ["size"]),
        (IRK.PtrWrite, ["size"]),
        (IRK.PushInt, ["value"]),
        (IRK.PushLabel, ["label"]),
        (IRK.ReturnVoid, []),
        (IRK.SetArgTemp, ["n"]),
        (IRK.SetLocal, ["local", "n"]),
        (IRK.SetLocalArg, ["local", "arg"]),
        (IRK.StoreTemp, ["n"]),
    ]
    funcs = []
    for k, v in ir_structs:
        k_name = str(k).split(".")[1]
        func_name = f"print_ir_{snake_case(k_name)}"
        funcs.append((f"IRK_{k_name}", func_name))
        print(f"proc {func_name} self in")
        if len(v) == 0:
            print(f"    printf(\"(IR.{k_name})\\n\");")
        else:
            print(f"    printf(\"(IR.{k_name} \");")
        for i, field in enumerate(v):
            sep = ", " if i+1 < len(v) else ")\\n"
            print(f"    printf(\"{field}={printers[field]}{sep}\", u64@(self + TIR_INSTR_{field}));")
        print(f"end")
    print(f"proc print_ir ir in")
    print(f"    var k = ir_instr_kind(ir);")
    k, f = funcs[0]
    print(f"    if k == {k} then {f}(ir);")
    for k, f in funcs[1:]:
        print(f"    else if k == {k} then {f}(ir);")
    print(f"    else")
    print(f"        printf(\"Unknown IR Kind: %s\", ir_instr_kind_cstr(k));")
    print(f"    end")
    print(f"end")
