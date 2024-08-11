import os
import tree_sitter
import tree_sitter_cpp
from tree_sitter import Language, Parser

CPP_LANGUAGE = Language(tree_sitter_cpp.language())
parser = Parser(CPP_LANGUAGE)

def extract_class_member_declarations(code, class_name):
    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node

    member_declarations = []
    function_implementations = {}

    def traverse(node):
        nonlocal member_declarations, function_implementations
        if node.type == 'class_specifier' and node.child_by_field_name('name').text.decode() == class_name:
            for child in node.children:
                if child.type == 'field_declaration_list':
                    for field in child.children:
                        if field.type == 'function_declarator':
                            declarator_node = field.child_by_field_name('declarator')
                            if declarator_node:
                                function_name = declarator_node.text.decode()
                                member_declarations.append(function_name)
                        elif field.type == 'field_declaration':
                            for decl in field.children:
                                if decl.type == 'function_declarator':
                                    declarator_node = decl.child_by_field_name('declarator')
                                    if declarator_node:
                                        function_name = declarator_node.text.decode()
                                        member_declarations.append(function_name)
                        elif field.type == 'function_definition':
                            declarator_node = field.child_by_field_name('declarator')
                            if declarator_node:
                                function_name_node = declarator_node.child_by_field_name('declarator')
                                if function_name_node:
                                    function_name = function_name_node.text.decode()
                                    function_body = field.child_by_field_name('body')
                                    if function_body:
                                        function_implementations[function_name] = function_body.text.decode()
        for child in node.children:
            traverse(child)

    traverse(root_node)
    return member_declarations, function_implementations

def extract_function_implementations(code, function_names):
    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node

    function_implementations = {}

    def traverse(node):
        nonlocal function_implementations
        if node.type == 'function_definition':
            declarator_node = node.child_by_field_name('declarator')
            if declarator_node:
                function_name_node = declarator_node.child_by_field_name('declarator')
                if function_name_node:
                    function_name = function_name_node.text.decode()
                    if function_name in function_names:
                        function_body = node.child_by_field_name('body')
                        if function_body:
                            function_implementations[function_name] = function_body.text.decode()
        for child in node.children:
            traverse(child)

    traverse(root_node)
    return function_implementations

def traverse_codebase(codebase_path, class_name):
    member_declarations = set()
    member_implementations = {}

    # 第一步：遍历代码仓库，收集所有成员函数的声明
    for root, dirs, files in os.walk(codebase_path):
        for file in files:
            if file.endswith('.h'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    code = f.read()
                    declarations, implemenrations = extract_class_member_declarations(code, class_name)
                    member_declarations.update(declarations)
                    member_implementations.update(implemenrations)
    
    print(member_declarations)
    print(member_implementations)

    # 第二步：遍历代码仓库，查找成员函数的实现
    for root, dirs, files in os.walk(codebase_path):
        for file in files:
            if file.endswith('.cc'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    code = f.read()
                    function_implementations = extract_function_implementations(code, member_declarations)
                    member_implementations.update(function_implementations)

    return member_implementations

codebase_path = '/Users/bytedance/leveldb/db'
class_name = 'MemTable'

function_implementations = traverse_codebase(codebase_path, class_name)

for func_name, func_body in function_implementations.items():
    print(f"Function Name: {func_name}")
    print(f"Function Body: {func_body}")
    print("-" * 40)