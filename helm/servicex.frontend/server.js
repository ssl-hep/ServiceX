/* eslint-disable no-unused-vars */

console.log('ServiceX REST API starting ... ');

// const fs = require('fs');

const express = require('express');
// const session = require('express-session');
const https = require('https');
const http = require('http');
// const rRequest = require('request');

const config = require('./config/config.json');

// const gConfig = JSON.parse(fs.readFileSync(`${secretsPath}globus-conf/globus-config.json`));
// const auth = Buffer.from(`${gConfig.CLIENT_ID}:${gConfig.CLIENT_SECRET}`).toString('base64');

console.log(config);

const app = express();
app.use(express.static('web'));

app.use(express.json()); // to support JSON-encoded bodies

const ES = require('./esBackend');

const backend = new ES(config);
// require('./utils/drequest')(app, config, backend);
// require('./utils/dpath')(app, config, backend);
// const usr = require('./utils/user')(app, config, backend);


app.put('/drequest/status/:id/:status/:info?', async (req, res) => {
  const { id } = req.params;
  const { status } = req.params;
  let info = '';
  if (req.params.info) { info = req.params.info };
  console.log('update request status: ', id, status, info);

  backend.ChangeStatus(id, status, info);
  res.status(200).send('OK');
  res.status(200).send('OK');
});

app.put('/drequest/events_served/:id/:events', async (req, res) => {
  const { id } = req.params;
  let { events } = req.params;
  console.log('request: ', id, ' had ', events, 'events served.');

  events = parseInt(events, 10);
  backend.AddEventsServed(id, events);
  res.status(200).send('OK');
});

app.put('/drequest/events_processed/:id/:events', async (req, res) => {
  const { id } = req.params;
  let { events } = req.params;
  console.log('request: ', id, ' had ', events, 'events processed.');

  events = parseInt(events, 10);
  backend.AddEventsProcessed(id, events);
  res.status(200).send('OK');
});

app.get('/healthz', (_req, res) => {
  try {
    res.status(200).send('OK');
  } catch (err) {
    console.log('something wrong', err);
  }
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
