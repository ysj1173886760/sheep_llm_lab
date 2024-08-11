import os
import tree_sitter
import tree_sitter_cpp
from tree_sitter import Language, Parser

CPP_LANGUAGE = Language(tree_sitter_cpp.language())
parser = Parser()
parser.set_language(CPP_LANGUAGE)

def parse_cpp_file(file_path):
    with open(file_path, 'r') as file:
        code = file.read()

    tree = parser.parse(bytes(code, 'utf8'))
    root_node = tree.root_node

    function_bodies = {}
    current_namespace = []
    current_class = None

    def get_qualified_name(name, current_namespace, current_class):
        qualified_name = '::'.join(current_namespace)
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

    def traverse(node):
        nonlocal current_namespace, current_class

        if node.type == 'namespace_definition':
            namespace_name_node = node.child_by_field_name('name')
            if namespace_name_node:
                namespace_name = namespace_name_node.text.decode('utf-8')
                current_namespace.append(namespace_name)
            for child in node.children:
                traverse(child)
            if namespace_name_node:
                current_namespace.pop()
            return

        if node.type == 'class_specifier':
            class_name_node = node.child_by_field_name('name')
            if class_name_node:
                class_name = class_name_node.text.decode('utf-8')
                current_class = class_name
            for child in node.children:
                traverse(child)
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
                    body_node = node.child_by_field_name('body')
                    if body_node:
                        function_bodies[qualified_function_name] = body_node.text.decode('utf-8')

        for child in node.children:
            traverse(child)

    traverse(root_node)
    return function_bodies

# 遍历项目目录并解析所有C++文件
def parse_project(project_dir):
    function_bodies_map = {}

    for root, dirs, files in os.walk(project_dir):
        for file in files:
            if file.endswith('.cc') or file.endswith('.h'):
                file_path = os.path.join(root, file)
                function_bodies = parse_cpp_file(file_path)
                function_bodies_map[file_path] = function_bodies

    return function_bodies_map

# 示例用法
project_dir = '/Users/bytedance/leveldb/db'
function_bodies_map = parse_project(project_dir)

# 输出函数体
for file_path, function_bodies in function_bodies_map.items():
    print(f'File: {file_path}')
    for function_name, function_body in function_bodies.items():
        print(f'  Function: {function_name}')
        print(f'  Body: {function_body}')