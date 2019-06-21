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
  secretsPath = './kube/secrets/';
}

const gConfig = JSON.parse(fs.readFileSync(`${secretsPath}globus-conf/globus-config.json`));
const esConfig = JSON.parse(fs.readFileSync(`${secretsPath}elasticsearch/elasticsearch.json`));

config.ES_HOST = `http://${esConfig.ES_USER}:${esConfig.ES_PASS}@${esConfig.ES_HOST}:9200`;
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


require('./utils/drequest')(app, config);
require('./utils/dpath')(app, config);
const usr = require('./utils/user')(app, config);

// const requiresLogin = async (req, res, next) => {
//   // to be used as middleware

//   if (req.session.loggedIn !== true) {
//     const error = new Error('You must be logged in to view this page.');
//     error.status = 403;
//     return next(error);
//   }
//   return next();
// };

// called on every path
// app.use(function (req, res, next) {
//     next();
// })

// app.get('/delete/:jservice', requiresLogin, function (request, response) {
//     var jservice = request.params.jservice;
//     cleanup(jservice);
//     response.redirect("/index.html");
// });

// app.get('/log/:podname', requiresLogin, async function (request, response) {
//     var podname = request.params.podname;
//     plog = await get_log(podname);
//     console.log(plog.body);
//     response.render("podlog", { pod_name: podname, content: plog.body });
// });

app.get('/', async (request, response) => {
  // console.log('===========> / CALL');
  // console.log(request.session);
  // if (request.session.user_id) {
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
  response.render('index', request.session);
});

app.get('/about', async (req, res) => {
  res.render('about', req.session);
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
      res.render('index');
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
        console.log('error on geting username:\t', error);
      }
      console.log('body:\t', body);
      const user = new usr.User();
      user.id = body.sub;
      req.session.user_id = body.sub;
      const found = await user.load();
      if (found === false) {
        user.username = body.preferred_username;
        user.organization = body.organization;
        user.name = body.name;
        user.email = body.email;
        await user.write();
        // const mbody = {
        //   from: `${config.NAMESPACE}<${config.NAMESPACE}@servicex.uchicago.edu>`,
        //   to: user.email,
        //   subject: 'ServiceX membership',
        //   text: `Dear ${user.name}, \n\n\t
        //   You have been authorized.\n\n
        //   Best regards,\n\tServiceX mailing system.`,
        // }
        // user.sendMailToUser(mbody);
      }
      req.session.loggedIn = true;
      res.redirect('/');
    });
  });
});

app.get('/logout', (req, res) => {
  if (req.session.loggedIn) { // logout from Globus
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
  res.render('index');
});

app.use((err, _req, res, _next) => {
  console.error(err.stack);
  res.status(500).send(err.message);
});

if (config.HTTPS) {
  const privateKey = fs.readFileSync(`${secretsPath}https-certs/servicex.key.pem`);
  const certificate = fs.readFileSync(`${secretsPath}https-certs/servicex.cert.crt`);
  const credentials = { key: privateKey, cert: certificate };
  https.createServer(credentials, app).listen(443, () => {
    console.log('Your server is listening on port 443.');
  });
} else {
  http.createServer(app).listen(80, () => {
    console.log('Your server is listening on port 80.');
  });
}
