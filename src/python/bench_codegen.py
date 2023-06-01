import random

id_n = 0

def permutate(idents):
    ops = ["*", "+", "-", "and", "or"] # no divide or mod because divide by zero...
    n_sub_exprs = random.randint(2, 20);
    tokens = []
    tokens.append(random.choice(idents))
    tokens.append("=")
    for _ in range(n_sub_exprs):
        lhs = random.choice(idents)
        op = random.choice(ops)
        tokens.append(lhs)
        tokens.append(op)
    tokens.append(random.choice(idents))
    return tokens[0], " ".join(tokens)

def make_proc(id):
    ident = f"proc_{id_n}"
    idents = random.sample(list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
                           random.randint(3, 15))
    print(f"proc {ident} {', '.join(idents)} in")
    for _ in range(random.randint(5, 100)):
        var, line = permutate(idents)
        print(f"    {line};")
    print(f"    return {var};")
    print(f"end")
    return ident, idents

print(f"extern printf fmt, ...;")
procs = []
for _ in range(1000):
    procs.append(make_proc(id_n));
    id_n += 1

print(f"proc main in")
print(f"    var xxx = 0;")
for name, params in procs:
    print(f"    xxx = xxx + {name}({', '.join(list(map(str, range(len(params)))))});")
print(f"    printf(\"xxx = %d\\n\", xxx);")
print(f"end")
