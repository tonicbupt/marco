# coding: utf-8

from flask import Blueprint, request, g

from marco.ext import dot, gitlab
from marco.models.host import Host
from marco.models.container import Container
from marco.models.application import Application

from marco.utils import yaml_loads
from marco.views.utils import jsonify


bp = Blueprint('ajax', __name__, url_prefix='/ajax')


class AppNotReadyError(Exception):
    message = 'App not ready yet'


class AppNotFoundError(Exception):
    message = 'App not found'


def _get_app(id, validate_process=False):
    app = Application.get(id)
    if not app:
        raise AppNotFoundError()
    if validate_process and app.processing():
        raise AppNotReadyError()
    return app


@bp.route('/app/<name>/update', methods=['POST', ])
@jsonify
def update_app(name):
    to_version = request.form['to_version']
    cs = Container.get_multi_by_app_name(name)
    update_args = {}
    for c in cs:
        update_args.setdefault(c.application.version, []).append(c.host.ip)
    for version, hosts in update_args.iteritems():
        if version == to_version:
            continue
        hosts = list(set(hosts))
        dot.update_app(name, version, to_version, hosts)
    return {'r': 0}


@bp.route('/app/<app_id>/all_metrics')
@jsonify
def app_all_metric(app_id):
    app = _get_app(app_id)
    data = app.all_realtime_metric_data(
        int(request.args.get('time', 10)), int(request.args.get('limit', 100)))
    return {k: v.get('points', []) for k, v in data.iteritems()}


@bp.route('/app/<app_id>/metrics')
@jsonify
def app_metric(app_id):
    app = _get_app(app_id)
    metric_name = request.args.get('metric_name', 'cpu_usage')
    data = app.realtime_metric_data(metric_name)
    points = [{'series': 0, 'x': p[0], 'y': p[1]}
              for p in data.get('points', [])]
    return {'data': [{'key': data['name'], 'values': points}, ]}


@bp.route('/app/<app_id>/add', methods=['POST', ])
@jsonify
def app_add_container(app_id):
    host = Host.get(request.form['host_id'])
    daemon = request.form.get('daemon', 'false')
    if not host:
        return {'r': 1, 'msg': 'no such host'}

    app = _get_app(app_id, validate_process=True)
    return dot.add_container(app, host, daemon)


@bp.route('/app/<app_id>/build', methods=['POST', ])
@jsonify
def app_build_image(app_id):
    base = request.form['base']
    host = Host.get(request.form['host_id'])
    if not host:
        return {'r': 1, 'msg': 'no such host'}

    app = _get_app(app_id, validate_process=True)
    return dot.build_image(app, host, base)


@bp.route('/app/<app_id>/test', methods=['POST', ])
@jsonify
def app_test_app(app_id):
    host = Host.get(request.form['host_id'])
    if not host:
        return {'r': 1, 'msg': 'no such host'}

    app = _get_app(app_id, validate_process=True)
    return dot.test_app(app, host)


@bp.route('/app/<app_id>/remove', methods=['POST', ])
@jsonify
def app_remove_app(app_id):
    host = Host.get(request.form['host_id'])
    if not host:
        return {'r': 1, 'msg': 'no such host'}

    app = _get_app(app_id, validate_process=True)
    if app.name in ('marco', 'openids'):
        return {'r': 1, 'msg': '不允许下线这些'}
    return dot.remove_app(app, host)


@bp.route('/app/<app_id>/syncdb', methods=['POST', ])
@jsonify
def app_sync_db(app_id):
    app = _get_app(app_id)

    y = yaml_loads(app.app_yaml)
    schema = y.get('schema', '')
    if schema:
        sql = gitlab.getrawblob(app.gitlab_id, app.version, schema)
        return {'r': sql}
    return {'r': 0}


@bp.route('/container/remove', methods=['POST', ])
@jsonify
def remove_containers():

    def _filter_container(c):
        if not c:
            return False
        # XD
        if g.user.username == 'tonic':
            return True
        if c.application.name in ('marco', 'openids'):
            return False

    cids = request.form.getlist('cids[]')
    cs = [Container.get_by_container_id(cid) for cid in cids if cid]
    for c in filter(_filter_container, cs):
        dot.remove_container(c)
    return {'r': 0, 'msg': 'ok'}


@bp.errorhandler(AppNotReadyError)
@bp.errorhandler(AppNotFoundError)
@jsonify
def error_handler(error):
    return {'r': 1, 'msg': error.message}


@bp.before_request
@jsonify
def test_if_logged_in():
    if not g.user:
        return {'r': 1, 'msg': 'need login'}
