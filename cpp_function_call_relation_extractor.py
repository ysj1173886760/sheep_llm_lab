import os
import tree_sitter
import tree_sitter_cpp
from tree_sitter import Language, Parser

CPP_LANGUAGE = Language(tree_sitter_cpp.language())
parser = Parser(CPP_LANGUAGE)

def parse_cpp_file(file_path):
    with open(file_path, 'r') as file:
        code = file.read()

    tree = parser.parse(bytes(code, 'utf8'))
    root_node = tree.root_node

    function_calls = {}
    function_definitions = {}
    current_namespace = []
    current_class = None

    def get_qualified_name(name, current_namespace, current_class):
        # qualified_name = '::'.join(current_namespace)
        qualified_name = ''
        if current_class:
            if qualified_name:
                qualified_name += '::' + current_class
            else:
                qualified_name = current_class
        if qualified_name:
            qualified_name += '::' + name
        else:
            qualified_name = name
        return qualified_name

    def get_function_name_and_class(call_expression_node):
        function_node = call_expression_node.child_by_field_name('function')
        if function_node.type == 'field_expression':
            class_name = function_node.child_by_field_name('field').text.decode('utf-8')
            function_name = function_node.child_by_field_name('argument').text.decode('utf-8')
            return function_name, class_name
        else:
            function_name = function_node.text.decode('utf-8')
            return function_name, None

    def traverse(node, current_function=None):
        nonlocal current_namespace, current_class

        if node.type == 'namespace_definition':
            namespace_name_node = node.child_by_field_name('name')
            if namespace_name_node:
                namespace_name = namespace_name_node.text.decode('utf-8')
                current_namespace.append(namespace_name)
            for child in node.children:
                traverse(child, current_function)
            if namespace_name_node:
                current_namespace.pop()
            return

        if node.type == 'class_specifier':
            class_name_node = node.child_by_field_name('name')
            if class_name_node:
                class_name = class_name_node.text.decode('utf-8')
                current_class = class_name
            for child in node.children:
                traverse(child, current_function)
            if class_name_node:
                current_class = None
            return

        if node.type == 'function_definition':
            declarator_node = node.child_by_field_name('declarator')
            if declarator_node:
                function_name_node = declarator_node.child_by_field_name('declarator')
                if function_name_node:
                    function_name = function_name_node.text.decode('utf-8')
                    qualified_function_name = get_qualified_name(function_name, current_namespace, current_class)
                    function_definitions[qualified_function_name] = node
                    current_function = qualified_function_name

        if node.type == 'call_expression':
            if current_function:
                function_name, class_name = get_function_name_and_class(node)
                if current_function not in function_calls:
                    function_calls[current_function] = []
                function_calls[current_function].append((function_name, class_name))

        for child in node.children:
            traverse(child, current_function)

    traverse(root_node)
    return function_definitions, function_calls

# 遍历项目目录并解析所有C++文件
def parse_project(project_dir):
    function_definitions_map = {}
    function_calls_map = {}

    for root, dirs, files in os.walk(project_dir):
        for file in files:
            if file.endswith('.cc') or file.endswith('.h'):
                file_path = os.path.join(root, file)
                function_definitions, function_calls = parse_cpp_file(file_path)
                function_definitions_map[file_path] = function_definitions
                function_calls_map[file_path] = function_calls

    return function_definitions_map, function_calls_map


# 示例用法
project_dir = '/Users/bytedance/leveldb/db'
function_definitions_map, function_calls_map = parse_project(project_dir)

# 输出函数调用关系
for file_path, function_calls in function_calls_map.items():
    print(f'File: {file_path}')
    for caller, callees in function_calls.items():
        for callee in callees:
            print(f'  {caller} -> {callee}')