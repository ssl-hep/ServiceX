const elasticsearch = require('elasticsearch');

module.exports = function usermodule(app, config) {
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
      this.es = new elasticsearch.Client({ host: config.ES_HOST, log: 'error' });
      // this.mg = require('mailgun-js')({ apiKey: mg_config.APPROVAL_MG, domain: mg_config.MG_DOMAIN });
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
        const response = await this.es.index({
          index: 'servicex_users',
          type: 'docs',
          id: this.id,
          refresh: true,
          body: {
            username: this.username,
            affiliation: this.affiliation,
            user: this.name,
            email: this.email,
            event: config.NAMESPACE,
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
        const response = await this.es.deleteByQuery({
          index: 'servicex_users', type: 'docs',
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
        const response = await this.es.update({
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

      if (config.TESTING) {
        this.name = 'Test User';
        this.username = 'testUsername';
        this.email = 'test@email.com';
        this.affiliation = 'Test Institution';
        this.created_at = new Date().getTime();
        this.approved = true;
        this.approved_on = new Date().getTime();
        console.log('test user loaded.');
        return true;
      }

      try {
        const response = await this.es.search({
          index: 'servicex_users',
          type: 'docs',
          body: {
            query: {
              bool: {
                must: [
                  { match: { _id: this.id } },
                ],
              },
            },
          },
        });
        // console.log(response);
        if (response.hits.total == 0) {
          console.log('user not found.');
          return false;
        }

        console.log('User found.');
        var obj = response.hits.hits[0]._source;
        // console.log(obj);
        // var created_at = new Date(obj.created_at).toUTCString();
        // var approved_on = new Date(obj.approved_on).toUTCString();
        this.name = obj.user;
        this.email = obj.email;
        this.affiliation = obj.affiliation;
        this.created_at = obj.created_at;
        this.approved = obj.approved;
        this.approved_on = obj.approved_on;
        return true;
      } catch (err) {
        console.error(err)
      }
      console.log('Done.');
      return false;
    }

    async approve() {
      this.approved = true;
      this.approved_on = new Date().getTime();
      await this.update();
      const body = {
        from: config.NAMESPACE + '<' + config.NAMESPACE + '@maniac.uchicago.edu>',
        to: this.email,
        subject: 'Authorization approved',
        text: 'Dear ' + this.name + ', \n\n\t' +
          ' your request for access to ' + config.NAMESPACE +
          ' ML front has been approved.\n\nBest regards,\n\tML front Approval system.',
      }
      this.send_mail_to_user(body);
    }

    send_mail_to_user(data) {
      this.mg.messages().send(data, function (error, body) {
        console.log(body);
      });
    }

    ask_for_approval() {
      if (config.hasOwnProperty('APPROVAL_EMAIL')) {
        var link = 'https://' + config.SITENAME + '/authorize/' + this.id;
        var data = {
          from: config.NAMESPACE + '<' + config.NAMESPACE + '@maniac.uchicago.edu>',
          to: config.APPROVAL_EMAIL,
          subject: 'Authorization requested',
          text: 'Dear Sir/Madamme, \n\n\t' + this.name +
            ' affiliated with ' + this.affiliation +
            ' requested access to ' + config.NAMESPACE +
            ' ML front.\n\tTo approve it use this link ' + link +
            '. To deny the request simply delete this mail.\n\nBest regards,\n\tML front Approval system',
        }
        this.send_mail_to_user(data);
      }
      else {
        console.error("Approval person's mail or mailgun key not configured.");
      }
    }

    async add_service(service) {
      try {
        service.owner = this.id;
        service.timestamp = new Date().getTime();
        service.user = this.name;
        console.log('creating service in es: ', service);
        await this.es.index({
          index: 'ml_front', type: 'docs', body: service,
        }, function (err, resp, status) {
          console.log('from ES indexer:', resp);
        });
      } catch (err) {
        console.error(err)
      }
    }

    async terminate_service(name) {
      console.log('terminating service in ES: ', name, 'owned by', this.id);
      console.log('not implemented yet.');
      // try {
      //     const response = await this.es.update({
      //         index: 'ml_front', type: 'docs', id: this.id,
      //         body: {
      //             doc: {
      //                 "terminated_on": new Date().getTime(),
      //                 "terminated": true
      //             }
      //         }
      //     });
      //     console.log(response);
      // } catch (err) {
      //     console.error(err)
      // }
      console.log('Done.');
    }

    async get_all_requests() {
      console.log('getting all requests of user:', this.id);
      try {
        const resp = await this.es.search({
          index: 'servicex',
          type: 'docs',
          body: {
            query: { match: { user: this.id } },
            sort: { created_at: { order: 'desc' } },
          },
        });
        const toSend = [];
        if (resp.hits.total > 0) {
          // console.log(resp.hits.hits);
          for (let i = 0; i < resp.hits.hits.length; i++) {
            let obj = resp.hits.hits[i]._source;
            console.log(obj);
            const createdAt = new Date(obj.created_at).toUTCString();
            const lid = resp.hits.hits[i]._id;
            const link = `<a href="/drequest_update/${lid}"> ${lid}</a>`;
            const serv = [obj.name, obj.description, createdAt, obj.status, link];
            toSend.push(serv);
          }
        } else {
          console.log('no requests found.');
        }
        return toSend;
      } catch (err) {
        console.error(err)
      }
      return [];
    }

    print() {
      console.log('- user id', this.id);
      console.log('- user name', this.name);
      console.log('- email', this.email);
      console.log('- affiliation', this.affiliation);
      console.log('- created at', this.created_at);
      console.log('- approved', this.approved);
      console.log('- approved on', this.approved_on);
    }

    async get_all_users() {
      console.log('getting all users info from es.');
      try {
        const resp = await this.es.search({
          index: 'servicex_users', type: 'docs',
          body: {
            size: 1000,
            query: { match_all: {} },
            sort: { created_at: { order: 'desc' } },
          },
        });
        // console.log(resp);
        var toSend = [];
        if (resp.hits.total > 0) {
          // console.log("Users found:", resp.hits.hits);
          for (var i = 0; i < resp.hits.hits.length; i++) {
            var obj = resp.hits.hits[i]._source;
            // console.log(obj);
            var created_at = new Date(obj.created_at).toUTCString();
            var approved_on = new Date(obj.approved_on).toUTCString();
            var serv = [obj.user, obj.email, obj.affiliation, created_at, obj.approved, approved_on]
            toSend.push(serv);
          }
        } else {
          console.log('No users found.');
        }
        return toSend;
      } catch (err) {
        console.error(err)
      }
      console.log('Done.');
    }
  };

  //probably not needed.
  app.get('/user', function (req, res) {
    console.log('sending profile info back.');
    res.json({
      loggedIn: req.session.loggedIn,
      name: req.session.name,
      email: req.session.email,
      username: req.session.username,
      organization: req.session.organization,
      user_id: req.session.user_id,
      authorized: req.session.authorized,
    });
  });

  app.get('/users_data', async function (req, res) {
    console.log('Sending all users info...');
    var user = new module.User();
    var data = await user.get_all_users();
    res.status(200).send(data);
    console.log('Done.');
  });

  app.get('/profile', async function (req, res) {
    console.log('profile called!');
    res.render('profile', req.session);
  });

  app.get('/users', async function (req, res) {
    console.log('users called!');
    res.render('users', req.session);
  });

  app.get('/authorize/:user_id', async function (req, res) {
    console.log('Authorizing user...');
    var user = new module.User(req.params.user_id);
    await user.load();
    user.approve();
    res.render('users', req.session);
  });

  app.get('/get_requests', async (req, res) => {
    console.log('getting all requests!');
    const user = new module.User(req.session.user_id);
    const data = await user.get_all_requests();
    res.status(200).send(data);
  });

  return module;
}