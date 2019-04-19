'use strict';

const swaggerTools = require('swagger-tools');
const jsyaml = require('js-yaml');

const fs = require('fs');
const path = require('path');

const express = require('express');
const https = require('https');
const http = require('http');
const request = require('request');

console.log('ServiceX server starting ... ');

let config;
let privateKey;
let certificate;
let gConfig;

const testing = true;

if (testing) {
  config = require('./kube/config.json');
  privateKey = fs.readFileSync('./kube/secrets/servicex.key.pem');
  certificate = fs.readFileSync('./kube/secrets/servicex.cert.crt');
  // gConfig = require('./kube/secrets/globus-config.json');
} else {
  config = require('/etc/servicex/config.json');
  privateKey = fs.readFileSync('/etc/https-certs/key.pem');
  certificate = fs.readFileSync('/etc/https-certs/cert.pem');
  // gConfig = require('/etc/globus-conf/globus-config.json');
}
config.TESTING = testing;

// var auth = "Basic " + new Buffer(gConfig.CLIENT_ID + ":" + gConfig.CLIENT_SECRET).toString("base64");

console.log(config);

const credentials = { key: privateKey, cert: certificate };

var elasticsearch = require('elasticsearch');
const session = require('express-session');

// var cookie = require('cookie');

const app = express();
app.use(express.static('web'));

app.set('view engine', 'pug');
app.use(express.json()); // to support JSON-encoded bodies
app.use(session({
  secret: 'kujduhvbleflvpops', resave: false,
  saveUninitialized: true, cookie: { secure: false, maxAge: 3600000 },
}));

// const drequest =
require('./utils/drequest')(app, config);
const usr = require('./utils/user')(app, config);

// swagger stuff ----------------

// swaggerRouter configuration
const options = {
  swaggerUi: path.join(__dirname, '/swagger.json'),
  controllers: path.join(__dirname, './controllers'),
  useStubs: process.env.NODE_ENV === 'development', // Conditionally turn on stubs (mock mode)
};

// The Swagger document (require it, build it programmatically, fetch it from a URL, ...)
const spec = fs.readFileSync(path.join(__dirname, 'api/swagger.yaml'), 'utf8');
const swaggerDoc = jsyaml.safeLoad(spec);

// Initialize the Swagger middleware
swaggerTools.initializeMiddleware(swaggerDoc, function (middleware) {
  // Interpret Swagger resources and attach metadata to request - must be first in swagger-tools middleware chain
  app.use(middleware.swaggerMetadata());

  // Validate Swagger requests
  app.use(middleware.swaggerValidator());

  // Route validated requests to appropriate controller
  app.use(middleware.swaggerRouter(options));

  // Serve the Swagger documents and Swagger UI
  app.use(middleware.swaggerUi());
});
//--------------------------------




// k8s stuff
const kClient = require('kubernetes-client').Client;
const kConfig = require('kubernetes-client').config;

var kclient;

async function configureKube() {
  try {
    console.log('configuring k8s client');
    kclient = new kClient({ config: kConfig.getInCluster() });
    await kclient.loadSpec();
    console.log('client configured');
    return kclient;
  } catch (err) {
    console.log('error in configureKube\n', err);
    process.exit(2);
  }
}


const requiresLogin = async (req, res, next) => {
  // to be used as middleware

  if (req.session.loggedIn !== true) {
    const error = new Error('You must be logged in to view this page.');
    error.status = 403;
    return next(error);
  }
  return next();
};

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

app.get('/', async function (request, response) {
  console.log('===========> / CALL');
  console.log(request.session);
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
  console.log('===========> / DONE');
  response.render('index', request.session)
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
  if (config.TESTING) {
    const user = new usr.User('user.id');
    await user.load();
    console.log('fake loaded');
    // user.write();
    // console.log('fake written.');
    req.session.user_id = user.id;
    req.session.name = user.name;
    req.session.username = user.username;
    req.session.affiliation = user.affiliation;
    req.session.email = user.email;
    req.session.loggedIn = true;
    res.render('index', req.session);
  } else {
    const red = `${gConfig.AUTHORIZE_URI}?scope=urn%3Aglobus%3Aauth%3Ascope%3Aauth.globus.org%3Aview_identities+openid+email+profile&state=garbageString&redirect_uri=${gConfig.redirect_link}&response_type=code&client_id=${gConfig.CLIENT_ID}`;
    // console.log('redirecting to:', red);
    res.redirect(red);
  }
});

app.get('/authcallback', (req, res) => {
  console.log('AUTH CALLBACK query:', req.query);
  let code = req.query.code;
  if (code) {
    console.log('there is a code. first time around.');
    code = req.query.code;
    let state = req.query.state;
    console.log('AUTH CALLBACK code:', code, '\tstate:', state);
  } else {
    console.log('NO CODE call...');
  }

  red = `${gConfig.TOKEN_URI}?grant_type=authorization_code&redirect_uri=${gConfig.redirect_link}&code=${code}`;

  let requestOptions = {
    uri: red, method: 'POST', headers: { 'Authorization': auth }, json: true,
  };

  // console.log(requestOptions);

  request.post(requestOptions, function (error, response, body) {
    if (error) {
      console.log('failure...', err);
      res.render('index');
    }
    console.log('success');//, body);

    console.log('==========================\n getting name.');
    id_red = 'https://auth.globus.org/v2/oauth2/userinfo';
    let idrequestOptions = {
      uri: id_red, method: 'POST', json: true,
      headers: { 'Authorization': `Bearer ${body.access_token}` },
    };

    request.post(idrequestOptions, async function (error, response, body) {
      if (error) {
        console.log('error on geting username:\t', error);
      }
      console.log('body:\t', body);
      const user = new usr.User();
      user.id = req.session.user_id = body.sub;
      user.username = req.session.username = body.preferred_username;
      user.affiliation = req.session.organization = body.organization;
      user.name = req.session.name = body.name;
      user.email = req.session.email = body.email;
      var found = await user.get();
      if (found === false) {
        await user.create();
        var body = {
          from: config.NAMESPACE + '<' + config.NAMESPACE + '@maniac.uchicago.edu>',
          to: user.email,
          subject: 'GATES membership',
          text: 'Dear ' + user.name + ', \n\n\t' +
            ' Your have been added to GATES. You may create a new team and run experiments. To be added to an existing team ask one of its members to add you to it (provide your username).' +
            '\n\nBest regards,\n\tGATES mailing system.',
        }
        user.send_mail_to_user(body);
        await user.get(); // so user.id gets filled up
      }
      req.session.loggedIn = true;
      req.session.teams = await user.get_teams();
      req.session.selected_team = null;
      req.session.selected_experiment = null;
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

    request.get(requestOptions, (error, response, body) => {
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
  console.error('Error in error handler: ', err.message);
  res.status(err.status).send(err.message);
});


if (!testing) {
  https.createServer(credentials, app).listen(443);

  // redirects if someone comes on http.
  http.createServer((req, res) => {
    res.writeHead(302, { Location: `https://${config.SITENAME}` });
    res.end();
  }).listen(80);
} else {
  http.createServer(app).listen(8080, () => {
    console.log('Your server is listening on port %d (http://localhost:%d)', 8080, 8080);
    console.log('Swagger-ui is available on http://localhost:%d/docs', 8080);
  });
}


async function main() {
  try {
    if (!testing) {
      await configureKube();
    }
  } catch (err) {
    console.error('Error: ', err);
  }
}

main();