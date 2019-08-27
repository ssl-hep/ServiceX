/* eslint-disable no-unused-vars */

const elasticsearch = require('@elastic/elasticsearch');
const fs = require('fs');

class ES {
  constructor(config) {
    const esConfig = JSON.parse(fs.readFileSync(`${config.SECRETS_PATH}elasticsearch/elasticsearch.json`));
    console.log(esConfig);
    const host = `http://${esConfig.ES_USER}:${esConfig.ES_PASS}@${esConfig.ES_HOST}:9200`;
    this.es = new elasticsearch.Client({ node: host, log: 'error' });
  }

  async CreateRequest(request) {
    request.status = 'Created';
    request.created_at = new Date().getTime();
    request.modified_at = new Date().getTime();
    request.events_processed = 0;
    request.events_served = 0;
    request.events_ready = 0;
    request.consumers = 0;
    request.paused_transforms = false;
    request.info = 'Created<BR>';
    await this.es.index({
      index: 'servicex',
      type: 'docs',
      refresh: true,
      body: request,
    }, (err, resp) => {
      if (err) {
        console.error('error in indexing new request:', err.meta.body.error);
        return null;
      }
      // need to check what is resp
      console.log(resp);
      const reqId = '';
      // this query needs to return generated requestID.
      // if (resp.body.hits.total === 0) {
      // return null;
      // }
      // return resp.body.hits.hits[0];
      return reqId;
    });
  }

  async GetReq(reqId) {
    await this.es.search({
      index: 'servicex',
      type: 'docs',
      id: reqId,
    }, (err, resp) => {
      if (err) {
        console.error('error in getting request with an id:', err.meta.body.error);
        return null;
      }
      if (resp.body.hits.total === 0) {
        return null;
      }
      return resp.body.hits.hits[0];
    });
  }

  async GetReqInStatus(status) {
    let request = false;
    await this.es.search({
      index: 'servicex',
      type: 'docs',
      body: {
        size: 1,
        query: {
          bool: {
            must: [{ match: { status } }],
          },
        },
      },
    }, (err, resp) => {
      if (err) {
        console.error('error in getting request in status:', err.meta.body.error);
        return;
      }
      if (resp.body.hits.total > 0) {
        request = resp.body.hits.hits[0];
      }
    });
    return request;
  }

  async ChangeStatus(reqId, nstatus, ainfo) {
    let cState = false;
    await this.es.update({
      index: 'servicex',
      type: 'docs',
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
      index: 'servicex_paths',
      type: 'docs',
      refresh: true,
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
      index: 'servicex_paths',
      type: 'docs',
      refresh: true,
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
      index: 'servicex_paths',
      type: 'docs',
      refresh: true,
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
      index: 'servicex_path',
      type: 'docs',
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


    let cState = false;
    this.es.update({
      index: 'servicex',
      type: 'docs',
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
        cState = resp.body.get._source;
      }
    });
    return cState;
  }

  EventsProcessed(reqId, type, nevents) {
    const scriptSource = 'ctx._source.events_processed += params.events';
    let cState = false;
    this.es.update({
      index: 'servicex',
      type: 'docs',
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
        cState = resp.body.get._source;
      }
    });
    return cState;
  }

  async CreatePath(path) {
    this.es.index({
      index: 'servicex_paths',
      type: 'docs',
      body: {
        req_id: path.req_id,
        status: 'Created',
        adler32: path.adler32,
        file_size: path.file_size,
        file_events: path.file_events,
        file_path: path.file_path,
        created_at: new Date().getTime(),
        last_accessed_at: new Date().getTime(),
        pause_transform: false,
      },
    }, (err, resp) => {
      if (err) {
        console.error('error in indexing new path:', err.meta.body.error);
      }
      console.log(resp);
    });
  }


}

module.exports = ES;
