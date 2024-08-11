import os
import tree_sitter
import tree_sitter_cpp
from tree_sitter import Language, Parser

CPP_LANGUAGE = Language(tree_sitter_cpp.language())
parser = Parser(CPP_LANGUAGE)

function_name = 'Build'

def extract_function_implementation(code, function_name):
    tree = parser.parse(bytes(code, 'utf8'))
    root_node = tree.root_node

    def traverse(node):
        if node.type == 'function_definition':
            function_node = node.child_by_field_name('declarator')
            if function_node and function_node.text.decode('utf8').startswith(function_name):
                return node.text.decode('utf8')
        for child in node.children:
            result = traverse(child)
            if result:
                return result
        return None

    return traverse(root_node)

def process_directory(directory, function_name):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.cc') or file.endswith('.h'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    code = f.read()
                    implementation = extract_function_implementation(code, function_name)
                    if implementation:
                        print(f'Found implementation in {file_path}:\n{implementation}\n')

# 指定代码仓库目录
code_repo_directory = '/Users/bytedance/leveldb'
process_directory(code_repo_directory, function_name)