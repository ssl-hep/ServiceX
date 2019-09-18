/* eslint-disable no-unused-vars */

console.log('ServiceX server starting ... ');

const fs = require('fs');

const express = require('express');
const session = require('express-session');
const https = require('https');
const http = require('http');
const rRequest = require('request');

const config = require('./config/config.json');

let secretsPath = '/etc/';

if (config.TESTING) {
  secretsPath = '../kube/secrets/';
}

const gConfig = JSON.parse(fs.readFileSync(`${secretsPath}globus-conf/globus-config.json`));
const auth = Buffer.from(`${gConfig.CLIENT_ID}:${gConfig.CLIENT_SECRET}`).toString('base64');

console.log(config);

const app = express();
app.use(express.static('web'));

app.set('view engine', 'pug');
app.use(express.json()); // to support JSON-encoded bodies
app.use(session({
  secret: 'kujduhvbleflvpops',
  resave: false,
  saveUninitialized: true,
  cookie: { secure: false, maxAge: 3600000 },
}));

// const requiresLogin = async (req, res, next) => {
//   // to be used as middleware
//   if (req.session.user.approved !== true) {
//     const error = new Error('You must be logged in to view this page.');
//     error.status = 403;
//     return next(error);
//   }
//   return next();
// };

app.get('/', async (req, res) => {
  // console.log('===========> / CALL');
  console.log(req.session);
  // if (req.session.user_id) {
  //     u = new usr.User(request.session.user_id);
  //     console.log("=====> refresh user info...");
  //     await u.get();
  //     console.log("=====> refresh teams list...");
  //     request.session.teams = await u.get_teams();
  //     if (request.session.team) {
  //         console.log('=====> refresh experiments list...');
  //         t = new tea.Team();
  //         if (request.session.team.id) {
  //             t.id = request.session.team.id;
  //             request.session.team.experiments = await t.get_experiments();
  //         }
  //     }
  // }
  // console.log('===========> / DONE');
  res.render('index', { user: req.session.user });
});

app.get('/about', async (req, res) => {
  res.render('about', { user: req.session.user });
});

app.get('/profile', async (req, res) => {
  console.log('profile called!');
  user_id = req.session.user.user_id;
  console.log('for user:', user_id)
  rRequest.get(config.FRONTEND + '/user/' + user_id, async (error, response, body) => {
    if (error) {
      console.error('error on looking up user in ES:\t', error);
    }
    // console.log('response:\t', response);
    req.session.user.details = JSON.parse(body);
    console.log('session user data:\t', req.session.user);
    res.render('profile', { user: req.session.user });
  });
});

app.get('/users', async (req, res) => {
  console.log('users called!');
  rRequest.get(config.FRONTEND + '/users/', async (error, response, body) => {
    if (error) {
      console.error('error on looking up all users in ES:\t', error);
    }
    // console.log('response:\t', response);
    const users_data = JSON.parse(body);
    console.log('all ES user data:\t', users_data);
    res.render('users', { user: req.session.user, users: users_data });
  });
});

app.get('/requests', async (req, res) => {
  console.log('requests called for user:', req.session.user);
  // req.session.user.user_id = 'c51dbd7e-d274-11e5-9b11-9be347a09ce0';
  rRequest.get(config.FRONTEND + '/user/requests/' + req.session.user.user_id, async (error, response, body) => {
    if (error) {
      console.error('error on looking up all users requests in ES:\t', error);
    }

    let requests_data = JSON.parse(body);
    for (re in requests_data) {
      requests_data[re].created_at = new Date(requests_data[re].created_at).toLocaleString();
    }
    console.log('all users requests:\t', requests_data.length);

    res.render('requests', { user: req.session.user, reqs: requests_data });
  });
});

app.get('/request/:reqId', async (req, res) => {
  console.log('request managing called!');
  const { reqId } = req.params;
  rRequest.get(config.FRONTEND + '/drequest/' + reqId, async (error, response, body) => {
    if (error) {
      console.error('error on looking up req_data in ES:\t', error);
    }
    // console.log('response:\t', response);
    let req_data = JSON.parse(body);
    req_data.reqId = reqId;
    console.log('req data:\t', req_data);
    res.render('request_view', { user: req.session.user, drequest: req_data });
  });
});

app.get('/request_create', async (req, res) => {
  console.log('request creation called!');
  res.render('request_create', { user: req.session.user });
});

app.post('/request_send', async (req, res) => {
  console.log('request sending off called!');
  let data = req.body;
  data.userid = req.session.user.user_id;
  console.log(' data:\t', data);

  var options = {
    uri: config.FRONTEND + '/drequest/create',
    method: 'POST',
    json: data,
  };

  rRequest(options, async (error, response, body) => {
    if (error) {
      console.error('error on creating new request in ES:\t', error);
    }
    // console.log('response:\t', response);
    console.log(body);
    // let req_data = JSON.parse(body);
    res.render('index', { user: req.session.user });
  });
});


app.get('/healthz', (_req, res) => {
  try {
    res.status(200).send('OK');
  } catch (err) {
    console.log('something wrong', err);
  }
});

app.get('/login', async (req, res) => {
  console.log('Logging in');
  const red = `${gConfig.AUTHORIZE_URI}?scope=urn%3Aglobus%3Aauth%3Ascope%3Aauth.globus.org%3Aview_identities+openid+email+profile&state=garbageString&redirect_uri=${gConfig.redirect_link}&response_type=code&client_id=${gConfig.CLIENT_ID}`;
  // console.log('redirecting to:', red);
  res.redirect(red);
});

app.get('/authcallback', (req, res) => {
  console.log('AUTH CALLBACK query:', req.query);
  const { code } = req.query;
  if (code) {
    console.log('there is a code. first time around.');
    console.log('AUTH CALLBACK code:', code, '\tstate:', req.query.state);
  } else {
    console.log('NO CODE call...');
  }

  const red = `${gConfig.TOKEN_URI}?grant_type=authorization_code&redirect_uri=${gConfig.redirect_link}&code=${code}`;

  const requestOptions = {
    uri: red, method: 'POST', headers: { Authorization: `Basic ${auth}` }, json: true,
  };

  // console.log(requestOptions);

  rRequest.post(requestOptions, (error1, response, body1) => {
    if (error1) {
      console.log('failure...', error1);
      req.session.user = {};
      res.render('index', { user: req.session.user });
    }
    console.log('success');

    console.log('==========================\n getting name.');
    const idRed = 'https://auth.globus.org/v2/oauth2/userinfo';
    const idrequestOptions = {
      uri: idRed,
      method: 'POST',
      json: true,
      headers: { Authorization: `Bearer ${body1.access_token}` },
    };

    rRequest.post(idrequestOptions, async (error, _response, body) => {
      if (error) {
        console.error('error on geting username:\t', error);
      }
      console.log('body:\t', body);
      user_id = body.sub;
      req.session.user = { user_id: user_id, approved: true };

      // get info on this user (from frontend).
      rRequest.get(config.FRONTEND + '/user/' + user_id, async (error, _response, esbody) => {
        if (error) {
          console.error('error on looking up user in ES:\t', error);
        }
        // console.log('response:\t', response);
        console.log('ES body:\t', esbody);
        // if not found create it.
        console.log('new session:', req.session);
        // if (found === false) {
        //   user.username = body.preferred_username;
        //   user.organization = body.organization;
        //   user.name = body.name;
        //   user.email = body.email;
        // const mbody = {
        //   from: `${ config.NAMESPACE } < ${ config.NAMESPACE }@servicex.uchicago.edu> `,
        //   to: user.email,
        //   subject: 'ServiceX membership',
        //   text: `Dear ${ user.name }, \n\n\t
        //   You have been authorized.\n\n
        //   Best regards,\n\tServiceX mailing system.`,
        // }
        // user.sendMailToUser(mbody);
        // }

      });

      // res.render('index', req.session);

      res.redirect('/');
    });
  });
});

app.get('/logout', (req, res) => {
  if (req.session.user.approved) { // logout from Globus
    const requestOptions = {
      uri: `https://auth.globus.org/v2/web/logout?client_id=${gConfig.CLIENT_ID}`,
      headers: {
        Authorization: `Bearer ${req.session.token}`,
      },
      json: true,
    };

    rRequest.get(requestOptions, (error, response, body) => {
      if (error) {
        console.log('logout failure...', error);
      }
      console.log('globus logout success.\n', response, body);
    });
  }
  req.session.destroy();
  res.render('index', { user: req.session.user });
});

app.use((err, _req, res, _next) => {
  console.error(err.stack);
  res.status(500).send(err.message);
});

http.createServer(app).listen(80, () => {
  console.log('Your server is listening on port 80.');
});
