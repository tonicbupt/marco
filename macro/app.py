# coding: utf-8

import os
import yaml

from flask import Flask
from werkzeug.utils import import_string

from macro.ext import db, etcd


blueprints = (
    'containers',
)


def load_config():
    config = {}
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
    with open(config_path, 'r') as f:
        config = yaml.load(f)
    return config


def create_app():
    config = load_config()
    os.environ.update(config)

    app = Flask(__name__)
    app.config.update(config)

    db.init_app(app)
    etcd.init_app(app)

    for bp in blueprints:
        import_name = '%s.views.%s:bp' % (__package__, bp)
        app.register_blueprint(import_string(import_name))

    return app
