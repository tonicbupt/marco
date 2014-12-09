# coding: utf-8

from werkzeug import cached_property

from marco.ext import db, es

from marco.models.consts import TaskType, TaskStatus, TaskResult
from marco.models.base import Base


repr_dict = {
    TaskType.AddContainer: u'增加容器',
    TaskType.RemoveContainer: u'下线容器',
    TaskType.UpdateContainer: u'更新容器',
    TaskType.BuildImage: u'构建镜像',
    TaskType.TestApplication: u'测试应用',
    TaskType.HostInfo: u'请求host信息',
}


apptype_dict = {
    TaskType.TestApplication: 'test',
    TaskType.BuildImage: 'build',
}


class Job(Base):

    __tablename__ = 'job'

    app_name = db.Column(db.String(255))
    app_version = db.Column(db.String(255))
    status = db.Column(db.Integer, nullable=False)
    succ = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.Integer, nullable=False)
    result = db.Column(db.String(255))
    created = db.Column(db.DateTime)
    finished = db.Column(db.DateTime)

    @classmethod
    def get(cls, id):
        return db.session.query(cls).filter(cls.id == id).one()

    @classmethod
    def get_multi(cls, app_name, app_version=None, status=None, succ=None, start=0, limit=20):
        q = db.session.query(cls).filter(cls.app_name == app_name)        
        if app_version is not None:
            q = q.filter(cls.app_version == app_version)
        if status is not None:
            q = q.filter(cls.status == status.value)
        if succ is not None:
            q = q.filter(cls.succ == succ.value)
        q = q.order_by(cls.id.desc()).offset(start)
        if limit is not None:
            q = q.limit(limit)
        return q.all()

    def success(self):
        return TaskResult(self.succ) == TaskResult.Succ

    def processing(self):
        return self.status == TaskStatus.Running.value

    def repr(self):
        return '%s: %s' % (self.create_time(), self.kind_cn())

    def create_time(self):
        return self.created.strftime('%Y-%m-%d %H:%M:%S')

    def finish_time(self):
        return self.finished and self.finished.strftime('%Y-%m-%d %H:%M:%S') or ''

    def kind_cn(self):
        return repr_dict[TaskType(self.kind)]

    def logs(self, size=100, timeout=1):
        apptype = apptype_dict.get(TaskType(self.kind), '')
        if not apptype:
            return []
        q = 'apptype:%s AND name:%s AND id:%s' % (apptype, self.app_name, self.id)
        r = es.search(q=q, size=size, sort='count', timeout=timeout)
        try:
            logs = [d['_source']['data'] for d in r['hits']['hits']]
        except:
            logs = []
        return logs

    @cached_property
    def application(self):
        from .application import Application
        return Application.get_by_name(self.app_name)

    @cached_property
    def appversion(self):
        from .application import AppVersion
        return AppVersion.get_by_name_and_version(self.app_name, self.app_version)

    @cached_property
    def test_id(self):
        if TaskType(self.kind) != TaskType.TestApplication:
            return ''
        return self.result.split('|', 1)[0]
