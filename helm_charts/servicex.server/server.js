/* eslint-disable no-unused-vars */

console.log('ServiceX server starting ... ');

const fs = require('fs');

const express = require('express');
const session = require('express-session');
const https = require('https');
const http = require('http');
const rRequest = require('request');
// const elasticsearch = require('@elastic/elasticsearch');

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

// require('./utils/drequest')(app, config, es);
// require('./utils/dpath')(app, config, es);
// const usr = require('./utils/user')(app, config, es);

// const requiresLogin = async (req, res, next) => {
//   // to be used as middleware
//   if (req.session.approved !== true) {
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
  res.render('index', req.session);
});

app.get('/about', async (req, res) => {
  res.render('about', req.session);
});

app.get('/profile', async (req, res) => {
  console.log('profile called!');
  user_id = req.session.user_id;
  console.log('for user:', user_id)
  req.session.approved = true;
  rRequest.get(config.FRONTEND + '/user/' + user_id, async (error, response, body) => {
    if (error) {
      console.error('error on looking up user in ES:\t', error);
    }
    // console.log('response:\t', response);
    req.session.user = JSON.parse(body);
    console.log('ES user data:\t', req.session);
    res.render('profile', req.session);
  });
});

app.get('/users', async (req, res) => {
  console.log('users called!');
  res.render('users', req.session);
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
      res.render('index', req.session);
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

      // get info on this user (from frontend).
      rRequest.get(config.FRONTEND + '/user/' + user_id, async (error, _response, esbody) => {
        if (error) {
          console.error('error on looking up user in ES:\t', error);
        }
        // console.log('response:\t', response);
        console.log('ES body:\t', esbody);
        // if not found create it.
        req.session.user_id = user_id;
        req.session.approved = true;
        console.log('new session:', req.session);
        // if (found === false) {
        //   user.username = body.preferred_username;
        //   user.organization = body.organization;
        //   user.name = body.name;
        //   user.email = body.email;
        // const mbody = {
        //   from: `${config.NAMESPACE}<${config.NAMESPACE}@servicex.uchicago.edu>`,
        //   to: user.email,
        //   subject: 'ServiceX membership',
        //   text: `Dear ${user.name}, \n\n\t
        //   You have been authorized.\n\n
        //   Best regards,\n\tServiceX mailing system.`,
        // }
        // user.sendMailToUser(mbody);
        // }

      });

      res.render('index', req.session);
    });
  });
});

app.get('/logout', (req, res) => {
  if (req.session.approved) { // logout from Globus
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
  res.render('index', req.session);
});

app.use((err, _req, res, _next) => {
  console.error(err.stack);
  res.status(500).send(err.message);
});

http.createServer(app).listen(80, () => {
  console.log('Your server is listening on port 80.');
});
