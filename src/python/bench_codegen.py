import random

id_n = 0

def permutate(idents):
    ops = ["*", "+", "-", "/", "and", "or", "%"]
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
    return " ".join(tokens)

def make_proc():
    global id_n
    id_n += 1
    ident = f"proc_{id_n}"
    idents = random.sample(list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
                           random.randint(3, 15))
    print(f"proc {ident} {', '.join(idents)} in")
    for _ in range(random.randint(5, 100)):
        print(f"    {permutate(idents)};")
    print(f"    return {random.choice(idents)};")
    print(f"end")

for _ in range(1000):
    make_proc();

print("proc main in end")
