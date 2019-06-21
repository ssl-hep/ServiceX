const elasticsearch = require('elasticsearch');

module.exports = function dpath(app, config) {
  const module = {};

  module.DApath = class DApath {
    constructor() {
      this.es = new elasticsearch.Client({ host: config.ES_HOST, log: 'error' });
      this.created_at = new Date().getTime();
      this.last_accessed_at = new Date().getTime();
    }

    async create(data) {
      console.log('adding request path to ES...', data);
      try {
        const response = await this.es.index({
          index: 'servicex_paths',
          type: 'docs',
          body: {
            req_id: data.req_id,
            status: 'Created',
            adler32: data.adler32,
            file_size: data.file_size,
            file_events: data.file_events,
            file_path: data.file_path,
            created_at: this.created_at,
            last_accessed_at: this.last_accessed_at,
          },
        });
        console.log(response);
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
    }

    async update() {
      console.log('Updating data request path info in ES...');
      try {
        // const response =
        await this.es.update({
          index: 'servicex_paths',
          type: 'docs',
          id: this.id,
          version: this.version,
          refresh: true,
          body: {
            doc: {
              status: this.status,
              last_accessed_at: this.last_accessed_at,
            },
          },
        });
        // console.log(response);
      } catch (err) {
        if (err.displayName === 'Conflict') {
          console.log('Conflict');
          return false;
        }
        console.error(err);
        return false;
      }
      console.log('Done.');
      return true;
    }

    async get(id) {
      console.log('getting path info for id:', id);
      try {
        const response = await this.es.search({
          index: 'servicex_paths',
          type: 'docs',
          body: {
            version: true,
            query: {
              match: { _id: id },
            },
          },
        });
        // console.log(response);
        if (response.hits.total === 0) {
          console.log('data access path not found.');
          return false;
        }
        console.log('data request path found.');
        const obj = response.hits.hits[0]._source;
        this.id = response.hits.hits[0]._id;
        this.version = response.hits.hits[0]._version;
        return obj;
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
      return false;
    }

    async getFromRequest(reqId, status) {
      console.log('getting path info for rid:', reqId, 'and status: ', status);
      try {
        const response = await this.es.search({
          index: 'servicex_paths',
          type: 'docs',
          body: {
            version: true,
            query: {
              bool: {
                must: [
                  { match: { req_id: reqId } },
                  { match: { status: status } },
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
        console.log('data request path found.');
        const obj = response.hits.hits[0]._source;
        this.id = response.hits.hits[0]._id;
        this.version = response.hits.hits[0]._version;
        return obj;
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
      return false;
    }

    async getValidated() {
      console.log('getting any validate path that should be transformed');
      try {
        const response = await this.es.search({
          index: 'servicex_paths',
          type: 'docs',
          body: {
            version: true,
            query: {
              match: { status: 'Validated' },
            },
          },
        });
        // console.log(response);
        if (response.hits.total === 0) {
          console.log('data access path not found.');
          return false;
        }
        console.log('data access path found.');
        const obj = response.hits.hits[0];
        this.id = obj._id;
        this.version = obj._version;
        return obj;
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
      return false;
    }

    // TODO - not finished.
    async getAll(rid) {
      console.log('getting ids of all paths of rid:', rid);
      try {
        const response = await this.es.search({
          index: 'servicex_paths',
          type: 'docs',
          body: {
            query: {
              bool: {
                must: [
                  { match: { req_id: rid } },
                ],
              },
            },
          },
        });
        // console.log(response);
        if (response.hits.total === 0) {
          console.log('no data access paths.');
          return [];
        }

        console.log('data access paths found.');
        // const obj = response.hits.hits[0]._source;
        // // console.log(obj);
        // this.id = response.hits.hits[0]._id;
        // this.name = obj.name;
        // this.description = obj.description;
        // this.dataset = obj.dataset;
        // this.columns = obj.columns;
        // this.events = obj.events;
        // this.status = obj.status;
        // this.info = obj.info;
        // this.dataset_size = obj.dataset_size;
        // this.dataset_files = obj.dataset_files;
        // this.dataset_events = obj.dataset_events;
        // this.events_served = obj.events_served;
        // this.events_processed = obj.events_processed;
        // this.created_at = obj.created_at;
        // return true;
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
      return false;
    }

    async getLastUsed(rid) {
      console.log('getting path info for last used path of rid:', rid);
      try {
        const response = await this.es.search({
          index: 'servicex_paths',
          type: 'docs',
          body: {
            size: 1,
            query: {
              match: { req_id: rid },
            },
            sort: {
              last_accessed_at: {
                order: 'desc',
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

  app.get('/dpath/:rid/:status?', async (req, res) => {
    const { rid } = req.params;
    let status = 'Created';
    if (req.params.status) {
      status = req.params.status;
    }
    console.log('getting a path belonging to request id: ', rid);
    const DApath = new module.DApath();
    const dap = await DApath.getFromRequest(rid, status);
    console.log('sending back:', dap);
    res.status(200).json(dap);
  });

  // gets all the info needed for the transformer to run
  // it changes state to Transforming
  app.get('/dpath/transform/', async (req, res) => {
    const DApath = new module.DApath();
    const dap = await DApath.getValidated();
    console.log('sending back:', dap);
    if (dap) {
      DApath.status = 'Transforming';
      const succ = await DApath.update();
      if (!succ) {
        res.status(200).json({});
      }
    }
    res.status(200).json(dap);
  });

  app.put('/dpath/status/:id/:status', async (req, res) => {
    const { id } = req.params;
    const { status } = req.params;
    console.log('post /dpath/status :', id, status);
    const DApath = new module.DApath();
    DApath.id = id;
    const found = await DApath.get(id);
    if (!found) {
      res.status(500).send('Bad request.');
    } else {
      DApath.status = status;
      DApath.last_accessed_at = new Date().getTime();
      DApath.update();
      res.status(200).send('OK');
    }
  });

  app.get('/dpath/:id', async (req, res) => {
    const { id } = req.params;
    console.log('getting a path with id: ', id);
    const DApath = new module.DApath();
    const dap = await DApath.get(id);
    console.log('sending back:', dap);
    res.status(200).json(dap);
  });

  app.get('/dpath/last_used/:rid', async (req, res) => {
    const { rid } = req.params;
    console.log('getting a last used path with rid: ', rid);
    const DApath = new module.DApath();
    const dap = await DApath.getLastUsed(rid);
    console.log('sending back:', dap);
    res.status(200).json(dap);
  });

  app.post('/dpath/create', async (req, res) => {
    const data = req.body;
    console.log('post /dpath/create :', data);
    const DApath = new module.DApath();
    await DApath.create(data);
    res.status(200).send('OK');
  });

  return module;
};
