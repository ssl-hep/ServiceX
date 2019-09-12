/* eslint-disable no-unused-vars */

const elasticsearch = require('@elastic/elasticsearch');
const fs = require('fs');

class ES {
  constructor(config) {
    this.esConfig = JSON.parse(fs.readFileSync(`${config.SECRETS_PATH}elasticsearch/elasticsearch.json`));
    console.log(this.esConfig);
    const host = `http://${this.esConfig.ES_USER}:${this.esConfig.ES_PASS}@${this.esConfig.ES_HOST}:9200`;
    this.es = new elasticsearch.Client({ node: host, log: 'error' });
    this.config = config;
  }


  UpdateStateServed(reqId, cState) {
    console.log('request state update:', cState)

    if (cState.events_served > 0 && cState.status === 'Validated') {
      this.ChangeStatus(reqId, 'Streaming', 'Started streaming.');
      return;
    }

    if (cState.events_served >= cState.events
      || cState.events_served >= cState.dataset_events) {
      console.log(`setting all paths for request ${reqId} to Done as sufficient events served.`);
      this.ChangeAllPathStatus(reqId, 'Done');
      return;
    }

    if ((cState.events_served - cState.events_processed) > this.config.HWM
      && cState.status !== 'Paused') {
      console.log(`pausing request ${reqId} as limit has been reached.`);
      this.ChangeStatus(reqId, 'Paused', 'Paused.');
      this.PausePaths(reqId);
      return;
    }

  }

  UpdateStateProcessed(reqId, cState) {
    console.log('request state update:', cState)

    if (cState.events_processed >= cState.events
      || cState.events_processed >= cState.dataset_events) {
      console.log(`setting request ${reqId} to Done as sufficient events processed.`);
      this.ChangeStatus(reqId, 'Done', 'Done.');
      this.ChangeAllPathStatus(reqId, 'Done');
      return;
    }

    if ((cState.events_served - cState.events_processed) < this.config.LWM
      && cState.status === 'Paused') {
      console.log(`unpausing request ${reqId} as LWM has been reached.`);
      this.ChangeStatus(reqId, 'Streaming', 'Restarted.');
      this.UnpausePaths(reqId);
      return;
    }
  }

  async CreateRequest(request) {
    request.status = 'Created';
    request.created_at = new Date().getTime();
    request.modified_at = new Date().getTime();
    request.events_processed = 0;
    request.events_served = 0;
    request.events_ready = 0;
    request.dataset_events = 0;
    request.dataset_files = 0;
    request.dataset_size = 0;
    request.consumers = 0;
    request.paused_transforms = false;
    request.info = 'Created';
    try {
      const response = await this.es.index({
        index: this.esConfig.REQ_TABLE,
        refresh: 'true',
        body: request,
      });
      // console.log(response);
      const reqId = response.body._id;
      // console.log('created request with reqId: ', reqId);
      return reqId;
    } catch (err) {
      console.error('error in indexing new request:', err.meta.body.error);
      return null;
    }
  }

  async UpdateRequest(update_body) {
    const reqId = update_body.reqId;
    delete update_body.reqId;
    console.log('update doc:', update_body);

    try {
      const resp = await this.es.update({
        index: this.esConfig.REQ_TABLE,
        id: reqId,
        retry_on_conflict: 3,
        body: {
          doc: update_body,
        },
      });

      if (resp.body.result === 'updated') {
        console.log('Updated.');
        return true;
      }

      console.error('did not update request?!');
      return false;

    } catch (err) {
      console.error('could not update request:', err);
      return false;
    }
  }

  async GetReq(reqId) {
    try {
      const response = await this.es.get({
        index: this.esConfig.REQ_TABLE,
        id: reqId,
      });
      console.log(response.body._source);
      return response.body._source;
    } catch (err) {
      console.error('error in getting request with an id:', reqId, err.meta.body.error);
      return null;
    }
  }

  async GetReqInStatus(status) {
    try {
      const response = await this.es.search({
        index: this.esConfig.REQ_TABLE,
        body: {
          size: 1,
          query: {
            bool: {
              must: [{ match: { status } }],
            },
          },
        },
      });
      if (response.body.hits.total.value > 0) {
        let hit = response.body.hits.hits[0];
        hit._source.reqId = hit._id;
        console.log('found req_id: ', hit._id);
        return hit._source;
      }
    } catch (err) {
      console.error('error in getting request in status:', err.meta.body.error);
      return null;
    }
  }

  async ChangeStatus(reqId, nstatus, ainfo) {
    let cState = false;
    ainfo = `\n${new Date().toLocaleString()} ${ainfo}`;
    await this.es.update({
      index: this.esConfig.REQ_TABLE,
      refresh: 'true',
      id: reqId,
      retry_on_conflict: 3,
      _source: ['status', 'info'],
      body: {
        script: {
          source: 'ctx._source.status=params.status;ctx._source.info += params.info; ',
          params: {
            status: nstatus,
            info: ainfo,
          },
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.error('could not update request status:', err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        cState = resp.body.get._source;
        console.log('new state:', cState);
      }
    });
    return cState;
  }

  async ChangeAllPathStatus(reqId, nstatus) {
    const sourceScript = `ctx._source.status = "${nstatus}"`;
    let updated = false;
    await this.es.updateByQuery({
      index: this.esConfig.PATH_TABLE,
      refresh: 'true',
      body: {
        query: { match: { req_id: reqId } },
        script: {
          source: sourceScript,
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.error('could not update path statuses:', err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        updated = true;
      }
    });
    return updated;
  }

  async PausePaths(reqId) {
    const sourceScript = 'ctx._source.status = "Paused"';
    let updated = false;
    await this.es.updateByQuery({
      index: this.esConfig.PATH_TABLE,
      refresh: 'true',
      body: {
        query: {
          bool: {
            must: [
              { match: { req_id: reqId } },
            ],
            should: [
              { match: { status: 'Validated' } },
              { match: { req_id: 'Transforming' } },
            ],
          },
        },
        script: {
          source: sourceScript,
        },
      },
    }, (err, resp, status) => {
      console.log(err, resp);
      if (err) {
        console.error('could not pause paths:', err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        updated = true;
      }
    });
    return updated;
  }

  async UnpausePaths(reqId) {
    const sourceScript = 'ctx._source.status = "Validated"';
    let updated = false;
    await this.es.updateByQuery({
      index: this.esConfig.PATH_TABLE,
      refresh: 'true',
      body: {
        query: {
          bool: {
            must: [
              { match: { req_id: reqId } },
              { match: { status: 'Paused' } },
            ],
          },
        },
        script: {
          source: sourceScript,
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.error('could not unpause paths:', err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        updated = true;
      }
    });
    return updated;
  }

  EventsServed(reqId, pathId, nevents) {
    const scriptSource = 'ctx._source.events_served += params.events';
    this.es.update({
      index: this.esConfig.PATH_TABLE,
      id: pathId,
      retry_on_conflict: 6,
      _source: ['events_served'],
      body: {
        script: {
          source: scriptSource,
          params: { events: nevents },
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.error('could not update events_served for path:', err.meta.body.error);
      }
    });

    this.es.update({
      index: this.esConfig.REQ_TABLE,
      id: reqId,
      retry_on_conflict: 6,
      _source: ['status', 'events_processed', 'events_served', 'events', 'dataset_events'],
      body: {
        script: {
          source: scriptSource,
          params: { events: nevents },
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.error('could not update events_served:', err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        // console.log(resp.body.get);
        this.UpdateStateServed(reqId, resp.body.get._source);
      }
    });
  }

  EventsProcessed(reqId, nevents) {
    const scriptSource = 'ctx._source.events_processed += params.events';
    this.es.update({
      index: this.esConfig.REQ_TABLE,
      id: reqId,
      retry_on_conflict: 6,
      _source: ['status', 'events_processed', 'events_served', 'events', 'dataset_events'],
      body: {
        script: {
          source: scriptSource,
          params: { events: nevents },
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.error('could not update events_processed:', err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        this.UpdateStateProcessed(reqId, resp.body.get._source);
      }
    });
  }

  // PATH STUFF

  async CreatePath(path) {
    this.es.index({
      index: this.esConfig.PATH_TABLE,
      body: {
        req_id: path.req_id,
        status: 'Created',
        adler32: path.adler32,
        file_size: path.file_size,
        file_events: path.file_events,
        file_path: path.file_path,
        events_served: 0,
        created_at: new Date().getTime(),
        last_accessed_at: new Date().getTime(),
        pause_transform: false,
        retries: 0,
        info: `${new Date().toLocaleString()} Created.`
      },
    }, (err, resp) => {
      if (err) {
        console.error('error in indexing new path:', err.meta.body.error);
      }
      console.log('path created with _id:', resp.body._id);
    });
  }

  async ChangePathStatus(pathId, nstatus, ainfo) {
    let cState = false;
    ainfo = `\n${new Date().toLocaleString()} ${ainfo}`;
    await this.es.update({
      index: this.esConfig.PATH_TABLE,
      refresh: 'true',
      id: pathId,
      retry_on_conflict: 3,
      _source: ['status', 'info'],
      body: {
        script: {
          source: 'ctx._source.status=params.status;ctx._source.info += params.info; ',
          params: {
            status: nstatus,
            info: ainfo,
          },
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.error('could not update path status:', err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        cState = resp.body.get._source;
        console.log('new state:', cState);
      }
    });
    return cState;
  }

  async GetPath(pathId) {
    try {
      const response = await this.es.get({
        index: this.esConfig.PATH_TABLE,
        id: pathId,
      });
      console.log(response.body._source);
      return response.body._source;
    } catch (err) {
      console.error('error in getting path with an id:', pathId, err.meta.body.error);
      return null;
    }
  }

  async GetPath(reqId, status) {
    try {
      const response = await this.es.search({
        index: this.esConfig.PATH_TABLE,
        body: {
          size: 1,
          query: {
            bool: {
              must: [
                { match: { req_id: reqId } },
                { match: { status: status } },
              ],
            },
          },
        }
      });
      console.log('paths found:', response.body.hits.total.value);
      if (response.body.hits.total.value > 0) {
        let hit = response.body.hits.hits[0];
        hit._source.pathId = hit._id;
        // console.log(hit._source);
        return hit._source;
      }
    } catch (err) {
      console.error('error in getting path from reqid:', reqId, err.meta.body.error);
      return null;
    }
  }

  async GetPathToTransform() {

    var path;
    var id;
    var seq;
    var primary;

    try {
      let response = await this.es.search({
        index: this.esConfig.PATH_TABLE,
        size: 1,
        body: {
          seq_no_primary_term: true,
          query: {
            bool: {
              must: [
                { match: { status: 'Validated' } },
              ],
            },
          },
        },
      });
      // console.log(response);
      response = response.body;
      if (response.hits.total.value === 0) {
        console.log('data access path not found.');
        return false;
      }
      const hit = response.hits.hits[0];
      // console.log('data access path found:\n', hit);
      path = hit._source;
      id = hit._id;
      path.pathId = id;
      seq = hit._seq_no;
      primary = hit._primary_term;
    } catch (err) {
      console.error(err);
      return false;
    }

    console.log('path found: \n', path, 'id:', id, '\nseq:', seq, '\nprimary:', primary);

    try {
      const response = await this.es.update({
        index: this.esConfig.PATH_TABLE,
        id: id,
        refresh: 'true',
        if_seq_no: seq,
        if_primary_term: primary,
        body: {
          script: {
            source: 'ctx._source.status="Transforming"; ',
          },
        }
      });

      if (response.body.result === 'updated') {
        console.log(`path ${id} updated to transforming.`);
        return path;
      }

    } catch (err) {
      console.error('issue in updating path to transforming:', err.meta.body.error);
      return false;
    }
  }

  // USER stuff

  async CreateUser(user) {
    user.created_at = new Date().getTime();
    const uid = user.userid;
    delete user.userid;
    if (user.approved === true) {
      user.approved_on = new Date().getTime();
    }
    try {
      const response = await this.es.index({
        index: this.esConfig.USER_TABLE,
        id: uid,
        refresh: 'true',
        body: user,
      });
      // console.log(response);
      console.log('created user with userId: ', response.body._id);
      return true;
    } catch (err) {
      console.error('error in creating new user:', err.meta.body.error);
      return false;
    }
  }

  async GetUserRequests(userId) {
    try {
      var resp = await this.es.search({
        index: this.esConfig.REQ_TABLE,
        size: 1000,
        body: {
          query: { match: { userid: userId } },
          sort: { created_at: { order: 'desc' } },
        },
      });
      const toSend = [];
      resp = resp.body;
      if (resp.hits.total.value > 0) {
        // console.log(resp.hits.hits);
        for (let i = 0; i < resp.hits.hits.length; i++) {
          const obj = resp.hits.hits[i]._source;
          obj.reqId = resp.hits.hits[i]._id;
          console.log(obj);
          toSend.push(obj);
        }
      } else {
        console.log('no requests found.');
      }
      return toSend;
    } catch (err) {
      console.error('could not get users requests', err);
    }
    return [];
  }

  async GetUsers() {
    const toSend = [];

    try {
      var resp = await this.es.search({
        index: this.esConfig.USER_TABLE,
        body: {
          size: 1000,
          query: { match_all: {} },
          sort: { created_at: { order: 'desc' } },
        },
      });
      // console.log(resp);
      resp = resp.body;
      console.log("Users found:", resp.hits.total.value);
      if (resp.hits.total.value > 0) {
        for (let i = 0; i < resp.hits.hits.length; i++) {
          const obj = resp.hits.hits[i]._source;
          // console.log(obj);
          const createdAt = new Date(obj.created_at).toLocaleString();
          const approvedOn = new Date(obj.approved_on).toLocaleString();
          const serv = [
            obj.user, obj.email, obj.organization,
            createdAt, obj.approved, approvedOn];
          toSend.push(serv);
        }
      }
    } catch (err) {
      console.error('error in getting all users profiles', err);
    }
    return toSend;
  }

  async GetUser(userId) {
    try {
      const response = await this.es.get({
        index: this.esConfig.USER_TABLE,
        id: userId,
      });
      console.log(response.body._source);
      return response.body._source;
    } catch (err) {
      console.error('error in getting userprofile with an userId:', userId, err.meta.body.error);
      return null;
    }
  }

  async ApproveUser(userId) {
    try {
      const response = await this.es.update({
        index: this.esConfig.USER_TABLE,
        id: userId,
        body: {
          script: {
            source: 'ctx._source.approved=true;',
          },
        },
      });
      console.log('result:', response.body.result);
      return 'Approved.';
    } catch (err) {
      console.error('error in approving user with an userId:', userId, err);
      return `Not approved: ${err}`;
    }
  }

  async DeleteUser(userId) {
    try {
      const response = await this.es.delete({
        index: this.esConfig.USER_TABLE,
        id: userId,
      });
      console.log('result:', response.body.result);
      return 'Deleted.';
    } catch (err) {
      console.error('error in deleting with an userId:', userId, err);
      return `Not deleted: ${err}`;
    }
  }

}

module.exports = ES;
