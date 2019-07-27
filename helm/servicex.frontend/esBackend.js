const elasticsearch = require('@elastic/elasticsearch');
const fs = require('fs');

class ES {

  constructor(config) {
    const esConfig = JSON.parse(fs.readFileSync(`${config.SECRETS_PATH}elasticsearch/elasticsearch.json`));
    console.log(esConfig);
    const host = `http://${esConfig.ES_USER}:${esConfig.ES_PASS}@${esConfig.ES_HOST}:9200`;
    this.es = new elasticsearch.Client({ node: host, log: 'error' });
  }

  ChangeStatus(reqId, status, info) {
    this.es.update({
      index: 'servicex',
      type: 'docs',
      id: reqId,
      retry_on_conflict: 3,
      _source: ['status', 'info'],
      body: {
        script: {
          source: 'ctx._source.status=params.status;ctx._source.info += params.info; ',
          params: {
            status: status,
            info: info,
          },
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.log('could not update request status:', err.meta.body.error);
      }
      if (resp.body.result === 'updated') {
        const cState = resp.body.get._source;
        console.log(cState);
      }
    });
  }

  AddEventsServed(reqId, events) {
    this.es.update({
      index: 'servicex',
      type: 'docs',
      id: reqId,
      retry_on_conflict: 3,
      _source: ['status', 'events_served', 'events_processed', 'events', 'dataset_events'],
      body: {
        script: {
          source: 'ctx._source.events_served += params.events',
          params: {
            "events": events,
          },
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.log('could not update events_served:', err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        const cState = resp.body.get._source;
        console.log(cState);
        if (cState.events_served >= cState.events || cState.events_served >= cState.dataset_events) {
          // this.ChangeStatus(reqID, 'Done', 'Done.');
          // should be paused.
        }
      }
    });
  }

  AddEventsProcessed(reqId, events) {
    this.es.update({
      index: 'servicex',
      type: 'docs',
      id: reqId,
      retry_on_conflict: 3,
      _source: ['status', 'events_served', 'events_processed', 'events', 'dataset_events'],
      body: {
        script: {
          source: 'ctx._source.events_processed += params.events',
          params: {
            events: events,
          },
        },
      },
    }, (err, resp, status) => {
      if (err) {
        console.log('could not update events_processed:', err.meta.body.error);
        return;
      }
      if (resp.body.result === 'updated') {
        const cState = resp.body.get._source;
        console.log(cState);
        if (cState.events_processed >= cState.events || cState.events_processed >= cState.dataset_events) {
          this.ChangeStatus(reqId, 'Done', 'Done.');
        }
      }
    });
  }
};

module.exports = ES