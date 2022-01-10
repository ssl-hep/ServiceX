# A script that will take as input a text (on the command line) and
# write out a zip file.
import sys
from servicex.code_generator_service.python_translator import PythonTranslator

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--text",
                        help="The text to be converted into zip file. STDIN if this is left off")
    parser.add_argument("-z", "--zipfile",
                        help="The name of the zip file to write out. STDOUT if this is left off")
    args = parser.parse_args()

    # Get the input text
    text = args.text if args.text is not None else sys.stdin.read().strip()

    # Output file
    translator = PythonTranslator()
    zip_data = translator.translate_text_python_to_zip(text)
    if args.zipfile is None:
        sys.stdout.buffer.write(zip_data)
    else:
        with open(args.zipfile, 'wb') as w:
            w.write(zip_data)
