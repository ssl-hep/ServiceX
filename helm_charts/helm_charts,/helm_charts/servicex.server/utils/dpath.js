const elasticsearch = require('elasticsearch');

module.exports = function dpath(app, config) {
  const module = {};

  module.DApath = class DApath {

    constructor(id = null) {
      this.es = new elasticsearch.Client({ host: config.ES_HOST, log: 'error' });
      this.created_at = new Date().getTime();
      this.last_accessed_at = new Date().getTime();
      if (id) {
        this.id = id;
      }
    }

    // TODO - not finished.
    async create(data) {
      console.log('adding request path to ES...', data);
      try {
        const response = await this.es.index({
          index: 'servicex_paths',
          type: 'docs',
          refresh: true,
          body: {
            //       name: this.name,
            //       user: userId,
            //       description: this.description,
            //       dataset: this.dataset,
            //       columns: this.columns,
            //       events: this.events,
            //       status: this.status,
            //       created_at: new Date().getTime(),
          },
        });
        console.log(response);
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
    }

    async get(id) {
      console.log('getting all path info for id:', id);
      try {
        const response = await this.es.search({
          index: 'servicex_paths',
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
          console.log('data access path not found.');
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
  };

  app.get('/dpath/:id', async (req, res) => {
    const { id } = req.params;
    console.log('getting a path with id: ', id);
    const DApath = new module.DApath();
    const dap = await DApath.get(id);
    console.log('sending back:', dap);
    res.status(200).json(dap);
  });

  app.post('/dpath_update', async (req, res) => {
    const data = req.body;
    console.log('post updating data access path:', data);
    // const darequest = new module.DArequest();
    // if (req.session.drequest.id) {
    //   console.log('has id getting existing data.');
    //   await darequest.get(req.session.drequest.id);
    // }
    // darequest.name = data.name;
    // darequest.description = data.description;
    // darequest.dataset = data.dataset;
    // darequest.columns = data.columns;
    // darequest.events = data.events;
    // if (req.session.drequest.id) {
    //   console.log('has id - updating.');
    //   await darequest.update();
    // } else {
    //   console.log('no id - creating drequest.');
    //   await darequest.create(req.session.user_id);
    // }
    res.status(200).send('OK');
  });

  return module;
};
