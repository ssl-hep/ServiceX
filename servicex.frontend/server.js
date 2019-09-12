/* eslint-disable no-unused-vars */

console.log('ServiceX REST API starting ... ');

// const fs = require('fs');

const express = require('express');
const https = require('https');
const http = require('http');
// const rRequest = require('request');

const config = require('./config/config.json');

console.log(config);

const app = express();

app.use(express.json()); // to support JSON-encoded bodies

const ES = require('./esBackend');

const backend = new ES(config);

// app.use(function (req, res, next) {
//   res.header("Access-Control-Allow-Origin", config.SITENAME);
//   res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept");
//   next();
// });

app.get('/healthz', (_req, res) => {
  try {
    res.status(200).send('OK');
  } catch (err) {
    console.log('something wrong', err);
  }
});

// REQUEST endpoints

app.get('/drequest/status/:status', async (req, res) => {
  const { status } = req.params;
  console.log(`getting a request in status: ${status}`);
  const request = await backend.GetReqInStatus(status);
  // console.log('sending back:', request);
  res.status(200).json(request);
});

app.get('/drequest/:reqId', async (req, res) => {
  const { reqId } = req.params;
  console.log('lookup request : ', reqId);
  const request = await backend.GetReq(reqId);
  if (request) {
    res.status(200).json(request);
  } else {
    res.status(500).send(`request ${reqId} not found.`);
  }
});

app.put('/drequest/status/:reqId/:status/:info?', async (req, res) => {
  const { reqId } = req.params;
  const { status } = req.params;
  let info = '';
  if (req.params.info) {
    info = req.params.info;
  }
  console.log('update request status: ', reqId, status, info);
  await backend.ChangeStatus(reqId, status, info);
  res.status(200).send('OK');
});

app.put('/events_served/:reqId/:pathId/:events', (req, res) => {
  const { reqId } = req.params;
  const { pathId } = req.params;
  let { events } = req.params;
  console.log('request: ', reqId, 'path:', pathId, 'had', events, 'events served.');

  events = parseInt(events, 10);
  backend.EventsServed(reqId, pathId, events);
  res.status(200).send('OK');
});

app.put('/events_processed/:reqId/:events', (req, res) => {
  const { reqId } = req.params;
  let { events } = req.params;
  console.log('request: ', reqId, 'had', events, 'events processed.');

  events = parseInt(events, 10);
  backend.EventsProcessed(reqId, events);
  res.status(200).send('OK');
});

app.put('/drequest/terminate/:reqId', async (req, res) => {
  const { reqId } = req.params;
  console.log(`request: ${reqId} will be terminated.`);
  backend.ChangeStatus(reqId, 'Terminated', 'User terminated.');
  backend.ChangeAllPathStatus(reqId, 'Terminated');
  res.status(200).send('OK');
});

app.post('/drequest/create/', async (req, res) => {
  const data = req.body;
  console.log('post creating data request:', data);
  if (!data.name) {
    res.status(500).send('Bad request. Request name missing.');
    return;
  }
  if (!data.dataset) {
    res.status(500).send('Bad request. Dataset name missing.');
    return;
  }
  if (!data.columns) {
    res.status(500).send('Bad request. Columns missing.');
    return;
  }
  if (!data.events) {
    res.status(500).send('Bad request. Events missing.');
    return;
  }
  if (!data.userid) {
    res.status(500).send('Bad request. userid missing.');
    return;
  }
  if (!data.description) {
    data.description = null;
  }
  const reqId = await backend.CreateRequest(data);
  if (reqId) {
    console.log('sending back reqId:', reqId);
    res.status(200).send(reqId);
  }
  else {
    req.status(500).send('Error in creating request.');
  }
});

// to be used by did-finder and validator
app.post('/drequest/update/', async (req, res) => {
  const data = req.body;
  console.log('post updating data request:', data);
  if (!data.req_id) {
    res.status(500).send('request has no req_id.');
    return;
  }

  const current_request = await backend.GetReq(data.req_id);
  if (current_request) {
    console.log('request found:', current_request);
    update_body = { reqId: data.req_id };
    if (data.status != current_request.status) update_body.status = data.status;
    if (data.dataset_size != current_request.dataset_size) update_body.dataset_size = data.dataset_size;
    if (data.dataset_events != current_request.dataset_events) update_body.dataset_events = data.dataset_events;
    if (data.dataset_files != current_request.dataset_files) update_body.dataset_files = data.dataset_files;
    if (data.info) update_body.info = `${current_request.info}\n${new Date().toLocaleString()} ${data.info}`;
    update_body.modified_at = new Date().getTime();
    const update_res = await backend.UpdateRequest(update_body);
    console.log('Update result:', update_res);
    if (update_res) {
      res.status(200).send('OK');
    } else {
      res.status(400).send('could not update request.');
    }
  } else {
    res.status(500).send(`request ${data.req_id} not found.`);
  }

  //   if (data.status) darequest.status = data.status;
  //   if (data.dataset) darequest.dataset = data.dataset;
  //   if (data.columns) darequest.columns = data.columns;
  //   if (data.events) darequest.events = data.events;
  //   if (data.kafka_lwm > -1) darequest.kafka_lwm = data.kafka_lwm;
  //   if (data.kafka_hwm > -1) darequest.kafka_hwm = data.kafka_hwm;
  //   if (data.redis_messages) darequest.redis_messages = data.redis_messages;
  //   if (data.redis_consumers) darequest.redis_consumers = data.redis_consumers;
});

// PATH endpoints

app.post('/dpath/create', async (req, res) => {
  const data = req.body;
  console.log('creating path:', data);
  backend.CreatePath(data);
  res.status(200).send('OK');
});

app.put('/dpath/status/:pathId/:status/:info?', async (req, res) => {
  const { pathId } = req.params;
  const { status } = req.params;
  let info = '';
  if (req.params.info) {
    info = req.params.info;
  }
  console.log(`update path status. id: ${pathId} status: ${status} info:${info}`);
  await backend.ChangePathStatus(pathId, status, info);
  res.status(200).send('OK');
});

app.get('/dpath/to_transform', async (req, res) => {
  console.log('getting path to transform');
  const path = await backend.GetPathToTransform();
  if (path) {
    res.status(200).json(path);
  } else {
    res.status(200).send(false);
  }
});

app.get('/dpath/:pathId', async (req, res) => {
  const { pathId } = req.params;
  console.log('lookup path:', pathId);
  const path = await backend.GetPath(pathId);
  if (path) {
    res.status(200).json(path);
  } else {
    res.status(500).send(`request ${pathId} not found.`);
  }
});

app.get('/dpath/:reqId/:status', async (req, res) => {
  const { reqId } = req.params;
  const { status } = req.params;
  console.log(`finding path belonging to request ${reqId} in status: ${status}`);
  const path = await backend.GetPath(reqId, status);
  if (path) {
    res.status(200).json(path);
  } else {
    res.status(500).send('no such path');
  }
});

// USER endpoints

app.post('/user/create', async (req, res) => {
  const data = req.body;
  console.log('post creating user:', data);
  if (!data.user) {
    res.status(500).send('Bad request. user missing.');
    return;
  }
  if (!data.username) {
    res.status(500).send('Bad request. username missing.');
    return;
  }
  if (!data.userid) {
    res.status(500).send('Bad request. userid missing.');
    return;
  }
  if (!data.organization) {
    res.status(500).send('Bad request. organization missing.');
    return;
  }
  if (!data.email) {
    res.status(500).send('Bad request. email missing.');
    return;
  }

  if (!data.approved) data.approved = false;

  const result = await backend.CreateUser(data);
  if (result) {
    console.log('User created.');
    res.status(200).send('OK');
  }
  else {
    req.status(500).send('Error in creating request.');
  }
});

app.get('/user/requests/:userId', async (req, res) => {
  const { userId } = req.params;
  console.log('lookup requests of user : ', userId);
  res.status(200).json(await backend.GetUserRequests(userId));
});

app.get('/users', async (req, res) => {
  console.log('lookup all users.');
  res.status(200).json(await backend.GetUsers());
});

app.get('/user/:userId', async (req, res) => {
  const { userId } = req.params;
  console.log('lookup user: ', userId);
  res.status(200).json(await backend.GetUser(userId));
});

app.put('/user/approve/:userId', async (req, res) => {
  const { userId } = req.params;
  console.log('approving user: ', userId);
  res.status(200).json(await backend.ApproveUser(userId));
});

app.delete('/user/:userId', async (req, res) => {
  const { userId } = req.params;
  console.log('deleting user: ', userId);
  res.status(200).json(await backend.DeleteUser(userId));
});

// THE REST
app.use((err, _req, res, _next) => {
  console.error(err.stack);
  res.status(500).send(err.message);
});

http.createServer(app).listen(80, () => {
  console.log('Your server is listening on port 80.');
});
