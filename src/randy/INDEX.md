# src/randy/
Self-hosting compiler source. All files are `#include`d from `main.randy` which is the single compilation unit.

## main.randy — entry point: CLI parsing, compilation phase orchestration, timing
```
main(argc: int, argv: ptr)
print_usage()
assemble_and_link(asm_path, obj_path, exe_path, ld_flags)
```

## lexer.randy — tokenization of source files, `#include` directive resolution
```
lex_file(path, include_paths: Vector[String&]&)
handle_include(src_file, line_no, tokens, include_paths, included_already, arg)
is_digit(c: char) -> bool
is_ident_start(c: char) -> bool
get_escaped_char(c: char) -> char
```

## token.randy — `Token` struct, `SrcLoc` struct, `TK` enum (90+ token kinds)
```
make_token(kind: TK, cstr, value, line, filename) -> Token&
token_kind_cstr(k: TK) -> cstr
token_kind_display(k: TK) -> cstr
print_token(self: Token&)
print_token_loc(self: Token&)
```

## token_stream.randy — `TokenStream` struct: token consumption with lookahead
```
TokenStream::new(tokens: Vector[Token&]&)
TokenStream::peek(self) / peekk(self) / peekk2(self)
TokenStream::next(self) / accept(self, kind) / expect(self, kind)
```

## parsing.randy — recursive descent parser, produces AST from token stream
```
parse_primary(ts, st, tt) -> Ast&
parse_def_type(ts, st, tt, is_instance)
parse_type(ts, st, tt, is_instance)
parse_var(ts, st, tt)
parse_if_else(ts, st, tt, expect)
parse_while(ts, st, tt)
parse_return(ts, st, tt)
parse_cast(ts, st, tt)
parse_sizeof(ts, st, tt)
parse_offsetof(ts, st, tt)
parse_static_assert(ts, st, tt)
```

## ast.randy — `Ast` struct (36+ node kinds via `AstK` enum), `Field`, `EnumValue`
```
// AstK enum: Ident, Integer, String, Call, BinOp, Return, VarDecl, VarAssign,
//   Def, IfElse, While, PointerRead, PointerWrite, Prefix, Const, Extern,
//   InlineAsm, Global, Break, Continue, Defer, AssignOp, Cast, Struct, MemberAccess,
//   AssignMember, SizeofExpr, SizeofType, Enum, Union, StaticAssert, OffsetOf,
//   TupleLiteral, TupleLength, TupleGet, ScopeResolve, GetReference, Index
Ast::new_ident / new_integer / new_string / new_call / new_binop / ...
ast_kind_cstr(k: AstK)
Field::make_copy(self)
```

## symbol_table.randy — `SymbolTable` struct: scoped identifier tracking
```
// SymbolKind enum: Undef, Const, Global, Def, Extern, Asm, Param, Local, Enum
st_make_symbol(st, kind, name, token) / st_get_symbol(st, name)
st_push_scope(st) / st_pop_scope(st) / st_depth(st)
symbol_kind(self) / symbol_name(self) / symbol_type(self) / symbol_token(self)
```

## type_table.randy — `TypeTable` struct: type registry, generic instantiation, scope management
```
// TypeKind enum: Undefined, Void, Any, Int_like, Reference, Def, Struct, Enum,
//   Union, GenericParam, Tuple, Slice, Array
make_type_table() -> TypeTable&
tt_any_type / tt_void_type / tt_int_type / tt_ptr_type / tt_cstr_type / tt_bool_type / tt_char_type
tt_push_scope / tt_pop_scope / tt_cur_scope / tt_top_scope
tt_get_type_name(tt, type) / tt_print_type_name(tt, type)
tt_get_or_create_slice_type(tt, elem_type) / tt_get_or_create_array_type(tt, elem_type, length)
types_eq(a, b) / types_assignable(tt, lhs, rhs)
make_type_struct / make_type_union / make_type_def / make_type_tuple
```

## type_infer.randy — two-phase type inference engine
```
TypeInfer::make_type_infer() / free_type_infer()
ti_infer_ident / ti_infer_integer / ti_infer_string / ti_infer_call
ti_infer_vector(self, tt, st, vector)
```

## type_checker.randy — semantic validation after type inference
```
TypeCheck::make_type_check() / free_type_check()
tc_check_body(self, tt, st, body)
tc_check_ident / tc_check_call
```

## compile_order.randy — reachability analysis: find code reachable from `main`
```
compile_order_main(roots, type_table, symbol_table) -> Vector[Ast&]&
```

## comptime_eval.randy — compile-time constant evaluation and static assertions
```
Interp::new() / is_const(name) / get_const(name) / add_const(name, ast)
comptime_eval_vector(interp, vector, st, tt, depth)
comptime_eval_binop / comptime_eval_call / comptime_eval_if_else / ...
```

## ir_context.randy — stack-based intermediate representation: 56+ instruction types
```
enum IrKind in GetLocal; PushLabel; PushInt; Call; OpAdd; OpSub; ... end
struct IrInstr in kind: IrKind; src_loc: SrcLoc&; slot_a/b/c: ptr; ... end
  methods: label() name() ident() n() nargs() value() varargs() size() offset() symbol() ...
struct IrContext in instructions; strings; externs; defs; globals; ... end
struct DefInfo in label: cstr; varargs: bool; end
struct GlobalInfo in kind: GlobalInfoKind; label: cstr; value: ptr; end
struct LocalInfo in n: int; offs: int; size: int; end
make_ir_push_int(value) / make_ir_call(label, varargs) / make_ir_goto(label) / ...
```

## ir_v2.randy — experimental alternative IR (MachineIR with register model)
```
MachineIR::new_nop()
MachineIRContext::new() / next_reg() / new_label()
```

## compiler_context.randy — assembly output accumulation and source file mapping
```
struct CompilerContext in out_lines; file_map; nodebug; ... end
CompilerContext::new(debug) -> CompilerContext&
cc_out(self, cstr) / cc_out_label(self, cstr) / cc_out_string(self, string)
cc_out_src_loc(self, src_loc) / cc_out_files(irctx, cctx)
```

## x86_64_backend.randy — x86_64 assembly emission (System V AMD64 ABI)
```
systemv_arg(n)
x86_64_emit_get_local / x86_64_emit_push_int / x86_64_emit_call / ...
```

## utils.randy — file I/O, hashing, string utilities
```
read_file_to_string(path: cstr) -> String&
cstr_hash(cstr) -> int / string_hash(string) -> int
int_from_string(string) -> int
min(a, b) / max(a, b)
CstrHashCompare (for Hashmap/Map key operations)
```

## bits.randy — platform constants (CHAR_BITS=8, INT_BITS=64, PTR_BITS=64)
