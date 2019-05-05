
console.log('ServiceX server starting ... ');

const swaggerTools = require('swagger-tools');
const jsyaml = require('js-yaml');

const fs = require('fs');
const path = require('path');

const express = require('express');
const session = require('express-session');
const https = require('https');
const http = require('http');
const rRequest = require('request');

// k8s stuff
const KClient = require('kubernetes-client').Client;
const kConfig = require('kubernetes-client').config;

const config = require('./config.json');

let secretsPath = '/etc/';

if (config.TESTING) {
  secretsPath = './kube/secrets/';
}

const privateKey = fs.readFileSync(`${secretsPath}https-certs/servicex.key.pem`);
const certificate = fs.readFileSync(`${secretsPath}https-certs/servicex.cert.crt`);
const gConfig = JSON.parse(fs.readFileSync(`${secretsPath}globus-conf/globus-config.json`));

// const auth = new Buffer(`${gConfig.CLIENT_ID}:${gConfig.CLIENT_SECRET}`).toString('base64');
const auth = Buffer.from(`${gConfig.CLIENT_ID}:${gConfig.CLIENT_SECRET}`).toString('base64');

console.log(config);

const credentials = { key: privateKey, cert: certificate };


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
swaggerTools.initializeMiddleware(swaggerDoc, (middleware) => {
  // Interpret Swagger resources and attach metadata to request
  // must be first in swagger-tools middleware chain
  app.use(middleware.swaggerMetadata());

  // Validate Swagger requests
  app.use(middleware.swaggerValidator());

  // Route validated requests to appropriate controller
  app.use(middleware.swaggerRouter(options));

  // Serve the Swagger documents and Swagger UI
  app.use(middleware.swaggerUi());
});
//--------------------------------

let kClient;

async function configureKube() {
  try {
    console.log('configuring k8s client');
    kClient = new KClient({ config: kConfig.getInCluster() });
    await kClient.loadSpec();
    console.log('client configured');
  } catch (err) {
    console.log('error in configureKube\n', err);
  }
  return kClient;
}


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
      req.session.username = body.preferred_username;
      req.session.organization = body.organization;
      req.session.name = body.name;
      req.session.email = body.email;
      const found = await user.load();
      if (found === false) {
        await user.write();
        // var body = {
        //   from: config.NAMESPACE + '<' + config.NAMESPACE + '@servicex.uchicago.edu>',
        //   to: user.email,
        //   subject: 'ServiceX membership',
        //   text: 'Dear ' + user.name + ', \n\n\t' +
        //     ' You've beed authorized.' +
        //     '\n\nBest regards,\n\tServiceX mailing system.',
        // }
        // user.send_mail_to_user(body);
        await user.load(); // so user.id gets filled up
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


app.use((err, _req, res) => {
  console.error('Error in error handler: ', err.message);
  res.status(err.status).send(err.message);
});


if (!config.TESTING) {
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
    if (!config.TESTING) {
      await configureKube();
      if (!kClient) {
        process.exit(2);
      }
    }
  } catch (err) {
    console.error('Error: ', err);
  }
}

main();
