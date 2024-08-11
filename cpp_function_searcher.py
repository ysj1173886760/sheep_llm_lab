import re
import os
import subprocess
import pickle
from collections import defaultdict

# 假设这些变量和函数已经在其他地方定义
env_trivial_threshold = 50
env_length_threshold = 3
ignored = ['for', 'if', 'while', 'switch', 'catch', 'VLOG', 'LOG', 'log', 'warn', 'log', 'trace', 'debug', 'defined', 'warn', 'error', 'fatal', 'static_cast', 'reinterpret_cast', 'const_cast', 'dynamic_cast', 'return', 'assert', 'sizeof', 'alignas', 'constexpr', 'set', 'get', 'printf', 'assert', 'ASSERT', 'CHECK', 'DCHECK_LT', 'DCHECK', 'DCHECK_EQ', 'DCHECK_GT', 'DCHECK_NE', 'UNLIKELY', 'LIKELY', 'unlikely', 'likely']

# 定义变量
cpp_filename_pattern = r'\.(c|cc|cpp|cu|C|h|hh|hpp|cuh|H)$'
ignore_pattern = ' '.join(f"--ignore '{pattern}'" for pattern in ['*test*', '*benchmark*', '*CMakeFiles*', '*contrib/*', '*third_party/*', '*thirdparty/*', '*3rd-[pP]arty/*', '*3rd[pP]arty/*', '*deps/*'])

RE_IDENTIFIER = r'\b[A-Za-z_]\w*\b'
RE_WS = r'(?:\s)'
RE_TWO_COLON = r'(?::{2})'
RE_SCOPED_IDENTIFIER = r'(?:' + RE_TWO_COLON + RE_WS + r'*)?(?:' + RE_IDENTIFIER + RE_WS + r'*' + RE_TWO_COLON + RE_WS + r'*)*[~]?' + RE_IDENTIFIER

def gen_nested_pair_re(L, R, others):
    simple_case = f"{others} {L} {others} {R} {others}"
    recursive_case = f"{others} {L}(?-1)*{R} {others}"
    nested = f"({recursive_case}|{simple_case})"
    return re.sub(r'\s+', '', f"(?:{L} {others} {nested}* {others} {R})")

RE_NESTED_PARENTHESES = gen_nested_pair_re(r'\(', r'\)', r'[^()]*')
RE_NESTED_BRACES = gen_nested_pair_re(r'{', r'}', r'[^^{}]*')

def gen_re_list(re_delimiter, re_item, optional):
    re_list = f"(?: {re_item} (?: {RE_WS}* {re_delimiter} {RE_WS}* {re_item})*? ) {optional}"
    return re.sub(r'\s+', '', re_list)

def gen_re_initializer_list_of_ctor():
    re_csv = gen_re_list(r',', r'[^,]+?', r'??')
    initializer = f"(?: {RE_SCOPED_IDENTIFIER} {RE_WS}* (?: (?: \\( {RE_WS}* {re_csv} {RE_WS}* \\) ) | (?: \\{{ {RE_WS}* {re_csv} {RE_WS}* \\}} ) ) )"
    re_csv_initializer = gen_re_list(r',', initializer, '')
    initializer_list = f"(?: (?<=\\) ) {RE_WS}* : {RE_WS}* {re_csv_initializer} {RE_WS}* (?={{) )"
    return re.sub(r'\s+', '', initializer_list)

RE_INITIALIZER_LIST = gen_re_initializer_list_of_ctor()

def gen_re_overload_operator():
    operators = r"[-+*/%^&|~!=<>]=?|(?:(?:<<|>>|\\|\\||&&)=?)|<=>|->\\*|->|\\(\\s*\\)|\\[\\s*\\]|\\+\\+|--|,"
    re_overload_operator = f"(?:operator {RE_WS}* (?:{operators}){RE_WS}*(?=\\())"
    return re.sub(r'\s+', '', re_overload_operator)

RE_OVERLOAD_OPERATOR = gen_re_overload_operator()

def gen_re_func_def():
    re_func_def = f"^.*?({RE_SCOPED_IDENTIFIER}|{RE_OVERLOAD_OPERATOR}) {RE_WS}* {RE_NESTED_PARENTHESES}(?:{RE_INITIALIZER_LIST})?{RE_WS}* {RE_NESTED_BRACES}"
    return re.sub(r'\s+', '', re_func_def)

RE_FUNC_DEFINITION = gen_re_func_def()

def gen_re_func_def_name():
    re_func_def_name = f"^.*?({RE_SCOPED_IDENTIFIER}|{RE_OVERLOAD_OPERATOR}) {RE_WS}* {RE_NESTED_PARENTHESES}"
    re_func_def_name = re_func_def_name.replace(' ', '')
    return re_func_def_name

RE_FUNC_DEFINITION_NAME = gen_re_func_def_name()

def gen_re_func_call():
    cs_tokens = f"{RE_WS}* (?:(?: {RE_SCOPED_IDENTIFIER} {RE_WS}* , {RE_WS}*)* {RE_SCOPED_IDENTIFIER} {RE_WS}*)?"
    re_func_call = f"((?:({RE_SCOPED_IDENTIFIER}) {RE_WS} *(?:\\({cs_tokens}\\))? {RE_WS}* (?: \\. | -> | :: ) {RE_WS}* )? ({RE_SCOPED_IDENTIFIER})) {RE_WS}* \\("
    return re.sub(r'\s+', '', re_func_call)

RE_FUNC_CALL = gen_re_func_call()

# 辅助函数
def merge_lines(lines):
    if multiline_break_enabled():
        return merge_lines_multiline_break_enabled(lines)
    else:
        return merge_lines_multiline_break_disabled(lines)

def merge_lines_multiline_break_enabled(lines):
    three_parts = [re.match(r'^([^:]+):(\d+):(.*)$', ln).groups() for ln in lines if re.match(r'^([^:]+):(\d+):(.*)$', ln)]
    prev_file, prev_lineno, prev_line = None, None, None
    result = []
    for i in range(len(three_parts)):
        if not three_parts[i]:
            if prev_file:
                result.append([prev_file, prev_lineno, three_parts[i - 1][1], prev_line])
                prev_file, prev_lineno, prev_line = None, None, None
        else:
            if prev_file:
                prev_line = prev_line + three_parts[i][2]
            else:
                prev_file, prev_lineno, prev_line = three_parts[i]
    if prev_file:
        result.append([prev_file, prev_lineno, three_parts[-1][1], prev_line])
    return result

def merge_lines_multiline_break_disabled(lines):
    three_parts = [re.match(r'^([^:]+):(\d+):(.*)$', ln).groups() for ln in lines if re.match(r'^([^:]+):(\d+):(.*)$', ln)]
    if not three_parts:
        return []
    prev_file, prev_lineno, prev_line = three_parts[0]
    prev_lineno_adjacent = prev_lineno
    result = []
    for i in range(1, len(three_parts)):
        file, lineno, line = three_parts[i]
        if file == prev_file and prev_lineno_adjacent + 1 == lineno:
            prev_line = prev_line + line
            prev_lineno_adjacent += 1
        else:
            result.append([prev_file, prev_lineno, three_parts[i][1], prev_line])
            prev_file, prev_lineno, prev_line = file, lineno, line
            prev_lineno_adjacent = prev_lineno
    result.append([prev_file, prev_lineno, three_parts[-1][1], prev_line])
    return result

def extract_all_callees(line, re_func_call):
    callees = []
    for match in re.finditer(re_func_call, line):
        callees.append({'call': match.group(1), 'prefix': match.group(2), 'name': match.group(3)})
    return callees

def simple_name(name):
    name = name.replace(' ', '')
    match = re.search(r'(~?\w+\b)$', name)
    return match.group(1) if match else name

def scope(name):
    match = re.search(r'\b(\w+)\b::\s*(~?\w+\b)$', name)
    return match.group(1) if match else None

def filename(file_info):
    match = re.search(r'/([^/]+)\.\w+:\d+', file_info)
    return match.group(1) if match else None

def is_pure_name(name):
    return all(c.isalpha() and c.islower() for c in name)

def restore_saved_files():
    saved_files = [f for f in os.listdir('.') if f.endswith('.saved_by_calltree')]
    for f in saved_files:
        original_f = f.replace('.saved_by_calltree', '')
        os.rename(f, original_f)

    tmp_files = [f for f in os.listdir('.') if f.endswith('.tmp.created_by_call_tree')]
    for f in tmp_files:
        os.remove(f)

def get_cache_or_run_keyed(key, file, func, *args):
    expect_key = '\0'.join(key)
    def check_key(data):
        return data.get('cached_key') == expect_key
    data = get_cached_or_run(lambda: {'cached_key': expect_key, 'cached_data': func(*args)}, check_key, file)
    return data['cached_data']

def get_cached_or_run(func, validate_func, cached_file, *args):
    if file_newer_than_script(cached_file):
        with open(cached_file, 'rb') as f:
            result = pickle.load(f)
        if result and isinstance(result, list) and validate_func(result):
            return result
    result = func(*args)
    with open(cached_file, 'wb') as f:
        pickle.dump(result, f)
    return result

def file_newer_than_script(file_b):
    script_path = get_path_of_script()
    return file_newer_than(file_b, script_path)

def file_newer_than(file_a, file_b):
    if not (os.path.isfile(file_a) and os.path.isfile(file_b)):
        return False
    return os.path.getmtime(file_a) > os.path.getmtime(file_b)

def get_path_of_script():
    script_path = os.path.abspath(__file__)
    return script_path

def multiline_break_enabled():
    result = subprocess.run(['ag', '--multiline-break', 'enabled'], capture_output=True, text=True)
    return 'enabled' in result.stdout

def extract_all_funcs(ignored, trivial_threshold, length_threshold):
    multiline_break = "--multiline-break" if multiline_break_enabled() else ""
    command = f"ag -U {multiline_break} -G {cpp_filename_pattern} {ignore_pattern} '{RE_FUNC_DEFINITION}'"
    print(command)
    matches = subprocess.run(command, shell=True, capture_output=True, text=True).stdout.strip().split('\n')
    matches = [ln + " " for ln in matches]

    print(f"extract lines: {len(matches)}")

    if not matches:
        raise RuntimeError("Current directory seems not a C/C++ project")

    func_file_line_def = merge_lines(matches)

    print(f"function definition after merge: {len(func_file_line_def)}")

    re_func_def_name = re.compile(RE_FUNC_DEFINITION_NAME)
    func_def = [ln[3] for ln in func_file_line_def]
    func_name = [re_func_def_name.search(ln).group(1) for ln in func_def]

    re_func_call = re.compile(RE_FUNC_CALL)
    print(f"re_function_call={RE_FUNC_CALL}")
    print("process callees: begin")
    func_callees = [extract_all_callees(ln, re_func_call) for ln in func_def]
    print("process callees: end")

    func_count = defaultdict(int)
    for callees in func_callees:
        for callee in callees:
            func_count[callee['name']] += 1

    trivial = {name: 1 for name in func_count if is_pure_name(name) and (func_count[name] > trivial_threshold or len(name) < length_threshold)}

    ignored = {**ignored, **trivial}
    reserved = {name: simple_name(name) for name in func_count if name not in ignored}

    func_file_line = [f"{ln[0]}:{ln[1]}" for ln in func_file_line_def]
    func_simple_name = [simple_name(name) for name in func_name]

    calling = defaultdict(list)
    called = defaultdict(list)
    no_callees = "[NO_CALLEES]"
    called[no_callees] = []

    for i in range(len(func_name)):
        file_info = func_file_line[i]
        caller_name = func_name[i]
        caller_simple_name = func_simple_name[i]
        scope_name = scope(caller_name)
        file_name = filename(file_info)
        file, start_lineno, end_lineno = func_file_line_def[i][:3]

        callees = func_callees[i]
        for seq, callee in enumerate(callees):
            callee['seq'] = seq

        callees = {f"{callee['prefix']}/{callee['name']}" if callee['prefix'] else callee['name']: callee for callee in callees if callee['name'] in reserved}
        callees = list(callees.values())
        callees = sorted(callees, key=lambda x: x['seq'])
        callee_name2simple = {callee['name']: simple_name(callee['name']) for callee in callees}

        caller_node = {
            'name': caller_name,
            'simple_name': caller_simple_name,
            'scope': scope_name,
            'file_info': file_info,
            'file': file,
            'start_lineno': start_lineno,
            'end_lineno': end_lineno,
            'filename': file_name,
            'callees': callees,
        }

        calling[caller_name].append(caller_node)

        if caller_name != caller_simple_name:
            calling[caller_simple_name].append(caller_node)

        processed_callee_names = set()
        for callee in callees:
            callee_name = callee['name']
            callee_simple_name = callee_name2simple[callee_name]
            if callee_name not in called:
                called[callee_name] = []
            called[callee_name].append(caller_node)
            processed_callee_names.add(callee_name)
            if callee_name != callee_simple_name and callee_simple_name not in processed_callee_names:
                if callee_simple_name not in called:
                    called[callee_simple_name] = []
                called[callee_simple_name].append(caller_node)
                processed_callee_names.add(callee_simple_name)

        if not callees:
            called[no_callees].append(caller_node)

    calling_names = sorted(calling.keys())
    called_names = sorted(called.keys())
    return dict(calling), dict(called), calling_names, called_names

def get_cached_or_extract_all_funcs(ignored, trivial_threshold, length_threshold):
    restore_saved_files()
    trivial_threshold = int(trivial_threshold)
    length_threshold = int(length_threshold)

    suffix = f"{trivial_threshold}.{length_threshold}"
    script_basename = os.path.basename(__file__).split('.')[0]
    file = f".{script_basename}.summary.{suffix}.dat"
    key = sorted(ignored) + [str(trivial_threshold), str(length_threshold)]
    do_summary = lambda: extract_all_funcs(ignored, trivial_threshold, length_threshold)
    result = get_cache_or_run_keyed(key, file, do_summary)
    return result

ignored_dict = {k: 1 for k in ignored}
calling, called, calling_names, called_names = get_cached_or_extract_all_funcs(ignored_dict, env_trivial_threshold, env_length_threshold)
print(calling, called, calling_names, called_names)