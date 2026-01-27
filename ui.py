import subprocess
from config import FZF_OPTS


def select(items, header, preview="", multi=True):
    args = FZF_OPTS.copy()
    args += ["--header", header]
    if multi:
        args.append("--multi")
    if preview:
        if "{}" not in preview:
            preview = preview + " {}"
        args += ["--preview", preview]

    fzf = subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    stdout, _ = fzf.communicate("\n".join(items))
    return stdout.strip().splitlines()


def select_one(items, header, preview=""):
    result = select(items, header, preview=preview, multi=False)
    return result[0] if result else None
