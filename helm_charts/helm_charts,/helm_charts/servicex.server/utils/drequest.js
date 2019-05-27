const elasticsearch = require('elasticsearch');

module.exports = function dreqmodule(app, config) {
  const module = {};

  module.DArequest = class DArequest {
    // statuses: Defined, Preparing, Ready to Serve, Serving, Done

    constructor(id = null) {
      this.es = new elasticsearch.Client({ host: config.ES_HOST, log: 'error' });
      this.created_at = new Date().getTime();
      this.status = 'Defined';
      if (id) {
        this.id = id;
      }
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
        this.info = obj.info;
        this.dataset_size = obj.dataset_size;
        this.dataset_files = obj.dataset_files;
        this.dataset_events = obj.dataset_events;
        this.events_served = obj.events_served;
        this.events_processed = obj.events_processed;
        this.created_at = obj.created_at;
        return true;
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
      return false;
    }

    async getWithStatus(status) {
      console.log('getting darequest with status:', status);
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
        if (response.hits.total === 0) {
          console.log('data access request not found.');
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
      try {
        const response = await this.es.update({
          index: 'servicex',
          type: 'docs',
          id: this.id,
          refresh: true,
          body: {
            doc: {
              status: this.status,
              events: this.events,
              dataset_size: this.dataset_size,
              dataset_files: this.dataset_files,
              dataset_events: this.dataset_events,
              events_processed: this.events_processed,
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

  app.get('/drequest/get/:status', async (req, res) => {
    const { status } = req.params;
    console.log('getting a request in status: ', status);
    const DAr = new module.DArequest();
    const dar = await DAr.getWithStatus(status);
    console.log('sending back:', dar);
    res.status(200).json(dar);
  });

  // to do: avoid all this property reassigning.
  app.get('/drequest_update/:rid', async (req, res) => {
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

  app.get('/drequest_prepare', async (req, res) => {
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

  app.get('/drequest_terminate', async (req, res) => {
    console.log('terminate request called: ', req.session.drequest.id);
    const darequest = new module.DArequest();
    await darequest.get(req.session.drequest.id);
    darequest.status = 'Done';
    console.log('has id - updating.');
    await darequest.update();
    req.session.drequest = {};
    console.log('Terminate done.');
    res.render('./drequest_manage', req.session);
  });

  app.get('/drequest_manage', async (req, res) => {
    console.log('manage requests called!');
    res.render('./drequest_manage', req.session);
  });

  app.post('/drequest_update', async (req, res) => {
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
    darequest.columns = data.columns;
    darequest.events = data.events;
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
