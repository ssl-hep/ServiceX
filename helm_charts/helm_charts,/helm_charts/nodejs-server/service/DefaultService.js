'use strict';


/**
 * Create a new data request
 *
 * body DataSpec 
 * returns inline_response_200
 **/
exports.dataPOST = function (body) {
  return new Promise(function (resolve, reject) {
    var examples = {};
    examples['application/json'] = {
      "request_id": "request_id"
    };
    if (Object.keys(examples).length > 0) {
      resolve(examples[Object.keys(examples)[0]]);
    } else {
      resolve();
    }
  });
}


/**
 * Request Status
 *
 * request_id String 
 * returns RequestStatus
 **/
exports.dataRequest_idGET = function (request_id) {
  return new Promise(function (resolve, reject) {
    var examples = {};
    examples['application/json'] = {
      "stats": {
        "events_processed": 5,
        "data_requested": 0.80082819046101150206595775671303272247314453125,
        "events_delivered": 5,
        "resets": 7,
        "data_ready": 1.46581298050294517310021547018550336360931396484375,
        "events_retried": 2,
        "events_requested": 6
      },
      "token": "token",
      "status": "initializing"
    };
    if (Object.keys(examples).length > 0) {
      resolve(examples[Object.keys(examples)[0]]);
    } else {
      resolve();
    }
  });
}


/**
 * for K8s deployment liveness probe
 *
 * no response value expected for this operation
 **/
exports.healthzGET = function () {
  return new Promise(function (resolve, reject) {
    resolve();
  });
}

