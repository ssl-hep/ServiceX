from flask import current_app, jsonify


def multiple_codegen_list():
    return jsonify(current_app.config.get('CODE_GEN_DICT'))