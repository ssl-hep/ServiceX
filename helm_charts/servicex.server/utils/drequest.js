const elasticsearch = require('@elastic/elasticsearch');

module.exports = function dreqmodule(app, config) {
  const module = {};

  module.DArequest = class DArequest {
    constructor() {
      this.es = new elasticsearch.Client({ node: config.ES_HOST, log: 'error' });
      this.created_at = new Date().getTime();
      this.status = 'Created';
      this.info = '';
      this.paused_transforms = false;
      this.events_processed = 0;
      this.events_served = 0;
    }

    async create(userId) {
      console.log('adding request to ES...');
      try {
        const response = await this.es.index({
          index: 'servicex',
          type: 'docs',
          refresh: true,
          body: {
            name: this.name,
            user: userId,
            description: this.description,
            dataset: this.dataset,
            columns: this.columns,
            events: this.events,
            status: this.status,
            created_at: new Date().getTime(),
            modified_at: new Date().getTime(),
            events_processed: 0,
            events_served: 0,
            kafka_lwm: 0,
            kafka_hwm: 0,
            paused_transforms: this.paused_transforms,
            info: 'Created\n',
          },
        });
        console.log(response);
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
    }

    async get(id) {
      console.log('getting darequest info...');
      try {
        const response = await this.es.search({
          index: 'servicex',
          type: 'docs',
          body: {
            query: {
              bool: {
                must: [
                  { match: { _id: id } },
                ],
              },
            },
          },
        });
        // console.log(response);
        response = response.body;
        if (response.hits.total === 0) {
          console.log('data access request not found.');
          return false;
        }

        console.log('data request found.');
        const obj = response.hits.hits[0]._source;
        // console.log(obj);
        this.id = response.hits.hits[0]._id;
        this.name = obj.name;
        this.description = obj.description;
        this.dataset = obj.dataset;
        this.columns = obj.columns;
        this.events = obj.events;
        this.status = obj.status;
        this.paused_transforms = obj.paused_transforms;
        this.info = obj.info;
        this.dataset_size = obj.dataset_size;
        this.dataset_files = obj.dataset_files;
        this.dataset_events = obj.dataset_events;
        this.events_served = obj.events_served;
        this.events_processed = obj.events_processed;
        this.created_at = obj.created_at;
        return response.hits.hits[0];
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
      return false;
    }

    async getWithStatus(status) {
      // console.log('getting darequest with status:', status);
      try {
        const response = await this.es.search({
          index: 'servicex',
          type: 'docs',
          body: {
            size: 1,
            query: {
              bool: {
                must: [
                  { match: { status } },
                ],
              },
            },
          },
        });
        // console.log(response);
        response = response.body;
        if (response.hits.total === 0) {
          // console.log('data access request not found.');
          return null;
        }
        console.log('data request found.');
        return response.hits.hits[0];
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
      return null;
    }

    async update() {
      console.log('Updating data request info in ES...');
      if ((this.kafka_hwm - this.kafka_lwm) > 10 && !this.paused_transforms) {
        this.pauseTransforms(true);
        this.paused_transforms = true;
      }
      if ((this.kafka_hwm - this.kafka_lwm) < 8 && this.paused_transforms) {
        this.pauseTransforms(false);
        this.paused_transforms = false;
      }
      try {
        const response = await this.es.update({
          index: 'servicex',
          type: 'docs',
          id: this.id,
          refresh: true,
          body: {
            doc: {
              name: this.name,
              description: this.description,
              status: this.status,
              info: this.info,
              events: this.events,
              dataset_size: this.dataset_size,
              dataset_files: this.dataset_files,
              dataset_events: this.dataset_events,
              events_served: this.events_served,
              events_processed: this.events_processed,
              kafka_lwm: this.kafka_lwm,
              kafka_hwm: this.kafka_hwm,
              paused_transforms: this.paused_transforms,
              modified_at: new Date().getTime(),
            },
          },
        });
        console.log(response);
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
    }

    async pauseTransforms(newState) {
      console.log('Pausing request in ES...');
      try {
        const response = await this.es.updateByQuery({
          index: 'servicex_paths',
          type: 'docs',
          refresh: true,
          body: {
            query: { match: { req_id: this.id } },
            script: {
              inline: `ctx._source.pause_transform = ${newState}`,
            },
          },
        });
        console.log(response);
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
    }

    async Terminate() {
      console.log('Terminating request in ES...');
      this.status = 'Terminated';
      this.update();
      try {
        const response = await this.es.updateByQuery({
          index: 'servicex_paths',
          type: 'docs',
          refresh: true,
          body: {
            query: { match: { req_id: this.id } },
            script: {
              inline: 'ctx._source.status = "Terminated"',
            },
          },
        });
        console.log(response);
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
    }
  };

  app.get('/drequest/status/:status', async (req, res) => {
    const { status } = req.params;
    // console.log('getting a request in status: ', status);
    const DAr = new module.DArequest();
    const dar = await DAr.getWithStatus(status);
    // console.log('sending back:', dar);
    res.status(200).json(dar);
  });

  app.get('/drequest/:id', async (req, res) => {
    const { id } = req.params;
    console.log('lookup request : ', id);
    const DAr = new module.DArequest();
    const result = await DAr.get(id);
    res.status(200).json(result);
  });

  app.put('/drequest/status/:id/:status/:info?', async (req, res) => {
    const { id } = req.params;
    const { status } = req.params;
    console.log('update request status: ', id, status);
    const DAr = new module.DArequest();
    await DAr.get(id);
    DAr.status = status;
    if (req.params.info) {
      DAr.info += req.params.info;
    }
    await DAr.update();
    res.status(200).send('OK');
  });

  app.put('/drequest/events_served/:id/:events', async (req, res) => {
    const { id } = req.params;
    const { events } = req.params;
    console.log('request: ', id, ' had ', events, 'events served.');
    const DAr = new module.DArequest();
    await DAr.get(id);
    DAr.events_served += parseInt(events, 10);
    await DAr.update();
    res.status(200).send('OK');
  });

  app.put('/drequest/events_processed/:id/:events', async (req, res) => {
    const { id } = req.params;
    const { events } = req.params;
    console.log('request: ', id, ' had ', events, 'events processed.');
    const DAr = new module.DArequest();
    await DAr.get(id);
    DAr.events_processed += parseInt(events, 10);
    if (DAr.events_processed === DAr.events) {
      DAr.status = 'Done';
      DAr.info += 'All events processed.';
    }
    await DAr.update();
    res.status(200).send('OK');
  });

  app.put('/drequest/terminate/:id', async (req, res) => {
    const { id } = req.params;
    console.log('request: ', id, ' will be terminated. ');
    const DAr = new module.DArequest();
    await DAr.get(id);
    DAr.Terminate();
    res.status(200).send('OK');
  });

  app.post('/drequest/create/', async (req, res) => {
    const data = req.body;
    console.log('post creating data request:', data);
    if (!data.name) {
      res.status(500).send('Bad request. Request name missing.');
      return;
    }
    if (!data.dataset) {
      res.status(500).send('Bad request. Dataset name missing.');
      return;
    }
    if (!data.columns) {
      res.status(500).send('Bad request. Columns missing.');
      return;
    }
    if (!data.events) {
      res.status(500).send('Bad request. Events missing.');
      return;
    }
    if (!data.userid) {
      res.status(500).send('Bad request. userid missing.');
      return;
    }
    const DAr = new module.DArequest();
    DAr.name = data.name;
    if (data.description) DAr.description = data.description;
    DAr.dataset = data.dataset;
    DAr.columns = data.columns;
    DAr.events = data.events;
    await DAr.create(data.userid);
    res.status(200).send('OK');
  });

  app.post('/drequest/update/', async (req, res) => {
    const data = req.body;
    console.log('post updating data request:', data);
    const darequest = new module.DArequest();
    const found = await darequest.get(data.id);
    if (!found) {
      res.status(500).send('Bad request');
      return;
    }
    if (data.name) darequest.name = data.name;
    if (data.description) darequest.description = data.description;
    if (data.status) darequest.status = data.status;
    if (data.dataset) darequest.dataset = data.dataset;
    if (data.columns) darequest.columns = data.columns;
    if (data.events) darequest.events = data.events;
    if (data.dataset_size) darequest.dataset_size = data.dataset_size;
    if (data.dataset_events) darequest.dataset_events = data.dataset_events;
    if (data.dataset_files) darequest.dataset_files = data.dataset_files;
    if (data.info) darequest.info += data.info;
    if (data.kafka_lwm > -1) darequest.kafka_lwm = data.kafka_lwm;
    if (data.kafka_hwm > -1) darequest.kafka_hwm = data.kafka_hwm;
    await darequest.update();
    res.status(200).send('OK');
  });


  // to do: avoid all this property reassigning.
  app.get('/wrequest_update/:rid', async (req, res) => {
    const { rid } = req.params;
    console.log('getting request ', rid);
    req.session.drequest = {};
    if (rid === 'new') {
      console.log('New request');
      res.render('drequest_update', req.session);
    } else {
      const dar = new module.DArequest();
      await dar.get(rid);
      req.session.drequest = {
        id: rid,
        name: dar.name,
        description: dar.description,
        dataset: dar.dataset,
        columns: dar.columns,
        events: dar.events,
        status: dar.status,
        info: dar.info,
        dataset_size: dar.dataset_size,
        dataset_files: dar.dataset_files,
        dataset_events: dar.dataset_events,
        events_served: dar.events_served,
        events_processed: dar.events_processed,
      };
      res.render('drequest_update', req.session);
    }
  });

  app.get('/wrequest_prepare', async (req, res) => {
    console.log('prepare request called: ', req.session.drequest.id);
    const darequest = new module.DArequest();
    await darequest.get(req.session.drequest.id);
    darequest.status = 'Preparing';
    console.log('has id - updating.');
    await darequest.update();
    req.session.drequest = {};
    console.log('Preparing done.');
    res.render('./drequest_manage', req.session);
  });

  app.get('/wrequest_terminate', async (req, res) => {
    console.log('terminate request called: ', req.session.drequest.id);
    const DAr = new module.DArequest();
    await DAr.get(req.session.drequest.id);
    DAr.Terminate();
    req.session.drequest = {};
    console.log('Terminate done.');
    res.render('./drequest_manage', req.session);
  });

  app.get('/wrequest_manage', async (req, res) => {
    console.log('manage requests called!');
    res.render('./drequest_manage', req.session);
  });

  app.post('/wrequest_update', async (req, res) => {
    const data = req.body;
    console.log('post updating data request:', data);
    const darequest = new module.DArequest();
    if (req.session.drequest.id) {
      console.log('has id getting existing data.');
      await darequest.get(req.session.drequest.id);
    }
    darequest.name = data.name;
    darequest.description = data.description;
    darequest.dataset = data.dataset;
    darequest.events = data.events;
    const cols = data.columns.replace(' ', '');
    darequest.columns = cols.split(',');

    if (req.session.drequest.id) {
      console.log('has id - updating.');
      await darequest.update();
    } else {
      console.log('no id - creating drequest.');
      await darequest.create(req.session.user_id);
    }
    res.status(200).send('OK');
  });

  return module;
};
