// const elasticsearch = require('@elastic/elasticsearch');

module.exports = function usermodule(app, config, es) {
  // if (!config.TESTING) {
  //     // var mg_config = require('/etc/mg-conf/config.json');
  // }
  // else {
  //     // var mg_config = require('../kube/test-ml/secrets/mg-config.json');
  // }
  // var mg = require('mailgun-js')({ apiKey: mg_config.APPROVAL_MG, domain: mg_config.MG_DOMAIN });

  const module = {};

  module.User = class User {
    constructor(id = null) {
      // this.es = new elasticsearch.Client({ node: config.ES_HOST, log: 'error' });
      // this.mg = require('mailgun-js')({
      // apiKey: mg_config.APPROVAL_MG,
      // domain: mg_config.MG_DOMAIN });
      this.approved_on = 0;
      this.approved = false;
      if (!config.APPROVAL_REQUIRED) {
        this.approved_on = new Date().getTime();
        this.approved = true;
      }
      this.created_at = new Date().getTime();
      // this.tzar = config.APPROVAL_EMAIL;
      if (id) {
        this.id = id;
      }
    }

    async write() {
      console.log('adding user to ES...');
      try {
        const response = await es.index({
          index: 'servicex_users',
          type: 'docs',
          id: this.id,
          refresh: true,
          body: {
            username: this.username,
            organization: this.organization,
            user: this.name,
            email: this.email,
            created_at: new Date().getTime(),
            approved: this.approved,
            approved_on: this.approved_on,
          },
        });
        console.log(response);
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
    }

    async delete() {
      console.log('deleting user from ES...');
      try {
        const response = await es.deleteByQuery({
          index: 'servicex_users',
          type: 'docs',
          body: { query: { match: { _id: this.id } } },
        });
        console.log(response);
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
    }

    async update() {
      console.log('Updating user info in ES...');
      try {
        const response = await es.update({
          index: 'servicex_users',
          type: 'docs',
          id: this.id,
          body: {
            doc: {
              approved_on: this.approved_on,
              approved: this.approved,
            },
          },
        });
        console.log(response);
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
    }

    async load() {
      console.log("getting user's info...");

      try {
        var response = await es.search({
          index: 'servicex_users',
          type: 'docs',
          body: {
            query: {
              match: { _id: this.id },
            },
          },
        });
        // console.log(response);
        response = response.body;
        if (response.hits.total === 0) {
          console.log('user not found.');
          return false;
        }

        console.log('User found.');
        const obj = response.hits.hits[0]._source;
        obj.id = response.hits.hits[0]._id;
        // console.log(obj);
        // var created_at = new Date(obj.created_at).toUTCString();
        // var approved_on = new Date(obj.approved_on).toUTCString();
        this.name = obj.user;
        this.email = obj.email;
        this.organization = obj.organization;
        this.created_at = obj.created_at;
        this.approved = obj.approved;
        this.approved_on = obj.approved_on;
        return obj;
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
      return false;
    }

    async approve() {
      this.approved = true;
      this.approved_on = new Date().getTime();
      await this.update();
      const body = {
        from: `${config.NAMESPACE}<${config.NAMESPACE}@maniac.uchicago.edu>`,
        to: this.email,
        subject: 'Authorization approved',
        text: `Dear ${this.name}, \n\n\t your request for access to ${config.NAMESPACE} 
        ML front has been approved.\n\nBest regards,\n\tML front Approval system.`,
      };
      this.send_mail_to_user(body);
    }

    sendMailToUser(data) {
      this.mg.messages().send(data, (error, body) => {
        console.log(body);
      });
    }

    askForApproval() {
      if (config.hasOwnProperty('APPROVAL_EMAIL')) {
        const link = `https://${config.SITENAME}/authorize/${this.id}`;
        const data = {
          from: `${config.NAMESPACE}<${config.NAMESPACE}@maniac.uchicago.edu>`,
          to: config.APPROVAL_EMAIL,
          subject: 'Authorization requested',
          text: `Dear Sir/Madamme, \n\n\t${this.name} 
          affiliated with ${this.organization} 
          requested access to ${config.NAMESPACE} ML front.
          \n\tTo approve it use this link ${link}. 
          To deny the request simply delete this mail.\n\n
          Best regards,\n\tML front Approval system`,
        };
        this.sendMailToUser(data);
      } else {
        console.error("Approval person's mail or mailgun key not configured.");
      }
    }

    async getRequests() {
      console.log('getting all requests of user:', this.id);
      try {
        var resp = await es.search({
          index: 'servicex',
          type: 'docs',
          body: {
            query: { match: { user: this.id } },
            sort: { created_at: { order: 'desc' } },
          },
        });
        const toSend = [];
        resp = resp.body;
        if (resp.hits.total > 0) {
          // console.log(resp.hits.hits);
          for (let i = 0; i < resp.hits.hits.length; i++) {
            const obj = resp.hits.hits[i]._source;
            obj.id = resp.hits.hits[i]._id;
            console.log(obj);
            toSend.push(obj);
          }
        } else {
          console.log('no requests found.');
        }
        return toSend;
      } catch (err) {
        console.error(err);
      }
      return [];
    }

    async getAllRequests() {
      console.log('getting all requests of user:', this.id);
      try {
        var resp = await es.search({
          index: 'servicex',
          type: 'docs',
          body: {
            query: { match: { user: this.id } },
            sort: { created_at: { order: 'desc' } },
          },
        });
        const toSend = [];
        resp = resp.body;
        if (resp.hits.total > 0) {
          // console.log(resp.hits.hits);
          for (let i = 0; i < resp.hits.hits.length; i++) {
            const obj = resp.hits.hits[i]._source;
            console.log(obj);
            const createdAt = new Date(obj.created_at).toUTCString();
            const lid = resp.hits.hits[i]._id;
            const link = `<a href="/wrequest_update/${lid}"> ${lid}</a>`;
            const serv = [obj.name, obj.description, createdAt, obj.status, link];
            toSend.push(serv);
          }
        } else {
          console.log('no requests found.');
        }
        return toSend;
      } catch (err) {
        console.error(err);
      }
      return [];
    }

    print() {
      console.log('- user id', this.id);
      console.log('- user name', this.name);
      console.log('- email', this.email);
      console.log('- organization', this.organization);
      console.log('- created at', this.created_at);
      console.log('- approved', this.approved);
      console.log('- approved on', this.approved_on);
    }

    async getAllUsers() {
      const toSend = [];
      console.log('getting all users info from es.');

      try {
        var resp = await es.search({
          index: 'servicex_users',
          type: 'docs',
          body: {
            size: 1000,
            query: { match_all: {} },
            sort: { created_at: { order: 'desc' } },
          },
        });
        // console.log(resp);
        resp = resp.body;
        if (resp.hits.total > 0) {
          // console.log("Users found:", resp.hits.hits);
          for (let i = 0; i < resp.hits.hits.length; i++) {
            const obj = resp.hits.hits[i]._source;
            // console.log(obj);
            const createdAt = new Date(obj.created_at).toUTCString();
            const approvedOn = new Date(obj.approved_on).toUTCString();
            const serv = [
              obj.user, obj.email, obj.organization,
              createdAt, obj.approved, approvedOn];
            toSend.push(serv);
          }
        }
      } catch (err) {
        console.error(err);
      }
      console.log('Done.');
      return toSend;
    }
  };


  app.get('/user/:user_id?', async (req, res) => {
    console.log('Returning user profile data...');
    let uid = null;
    if (req.params.user_id) { // rest API
      uid = req.params.user_id;
    } else if (req.session.user_id) { // from web site
      uid = req.session.user_id;
    }
    if (!uid) {
      res.status(500).send('user ID needed.');
    }
    const user = new module.User(uid);
    const userInfo = await user.load();
    res.json(userInfo);
  });

  app.get('/users_data', async (req, res) => {
    console.log('Sending all users info...');
    const user = new module.User();
    const data = await user.getAllUsers();
    res.status(200).send(data);
  });

  app.get('/user/requests/:user_id', async (req, res) => {
    console.log('Returning all user requests...');
    const user = new module.User(req.params.user_id);
    const data = await user.getRequests();
    res.status(200).json(data);
  });


  app.get('/profile', async (req, res) => {
    console.log('profile called!');
    const user = new module.User();
    user.id = req.session.user_id;
    req.session.approved = true;
    const userInfo = await user.load();
    res.render('profile', userInfo);
  });

  // simply renders users.pug which in turn gets data from /users_data
  app.get('/users', async (req, res) => {
    console.log('users called!');
    res.render('users');
  });


  app.get('/authorize/:user_id', async (req, res) => {
    console.log('Authorizing user...');
    const user = new module.User(req.params.user_id);
    await user.load();
    user.approve();
    res.render('users', req.session);
  });

  app.get('/get_requests', async (req, res) => {
    console.log('getting all requests!');
    const user = new module.User(req.session.user_id);
    const data = await user.getAllRequests();
    res.status(200).send(data);
  });

  return module;
};
