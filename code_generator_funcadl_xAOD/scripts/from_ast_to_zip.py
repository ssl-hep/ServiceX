# A script that will take as input a text ast (on the command line) and
# write out a zip file.
import sys
from servicex.code_generator_service.ast_translater import AstTranslater

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--ast",
                        help="The text AST to be converted into zip file. STDIN if this is left off")  # noqa: E501
    parser.add_argument("-z", "--zipfile",
                        help="The name of the zip file to write out. STDOUT if this is left off")
    parser.add_argument("--uproot",
                        help="Generate code to transform file using uproot",
                        action='store_true', default=False, required=False)
    parser.add_argument("--xaod",
                        help="Generate code to transform file using EventLoop",
                        action='store_true', default=False, required=False)

    args = parser.parse_args()

    if args.xaod == args.uproot:
        print("Please specify a target for generated code: Uproot or XAod")
        sys.exit(-1)

    if args.xaod:
        target_backend = 'xAOD'
    else:
        target_backend = 'uproot'

    # Get the input AST
    ast_text = args.ast if args.ast is not None else sys.stdin.read().strip()

    # Output file
    translator = AstTranslater(target_backend)
    zip_data = translator.translate_text_ast_to_zip(ast_text)
    if args.zipfile is None:
        sys.stdout.buffer.write(zip_data)
    else:
        with open(args.zipfile, 'wb') as w:
            w.write(zip_data)
