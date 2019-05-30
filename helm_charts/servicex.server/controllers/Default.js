var utils = require('../utils/writer.js');
var Default = require('../service/DefaultService');

module.exports.dataPOST = function dataPOST(req, res, next) {
  var body = req.swagger.params['body'].value;
  Default.dataPOST(body)
    .then(function (response) {
      utils.writeJson(res, response);
    })
    .catch(function (response) {
      utils.writeJson(res, response);
    });
};

// module.exports.dataRequest_idGET = function dataRequest_idGET(req, res, next) {
//   var request_id = req.swagger.params['request_id'].value;
//   Default.dataRequest_idGET(request_id)
//     .then(function (response) {
//       utils.writeJson(res, response);
//     })
//     .catch(function (response) {
//       utils.writeJson(res, response);
//     });
// };

module.exports.healthzGET = function healthzGET(req, res, next) {
  Default.healthzGET()
    .then(function (response) {
      utils.writeJson(res, response);
    })
    .catch(function (response) {
      utils.writeJson(res, response);
    });
};
