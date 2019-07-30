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

  async ChangePathStatus(reqId, nstatus) {
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

  AddEvents(reqId, type, nevents) {
    const scriptSource = `ctx._source.events_${type} += params.events`;
    let cState = false;
    this.es.update({
      index: 'servicex',
      type: 'docs',
      id: reqId,
      retry_on_conflict: 6,
      _source: ['status', 'events_served', 'events_processed', 'events', 'dataset_events'],
      body: {
        script: {
          source: scriptSource,
          params: { events: nevents },
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.error(`could not update events_${type}:`, err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        cState = resp.body.get._source;
      }
    });
    return cState;
  }
}

module.exports = ES;
