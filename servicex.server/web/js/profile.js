$(document).ready(function () {

    $.getJSON('https://servicex-frontend.uc.ssl-hep.org/user', function (data) {
        console.log(data);
        // var table = $('#users_table').DataTable({
        //     data: data,
        //     "paging": false,
        //     "searching": false,
        //     "aoColumns": [
        //         { "mData": 0, "sTitle": "Name", "sWidth": "20%" },
        //         { "mData": 1, "sTitle": "Email", "sWidth": "10%" },
        //         { "mData": 2, "sTitle": "Affiliation", "sWidth": "20%" },
        //         { "mData": 3, "sTitle": "Registered on", "sWidth": "20%" },
        //         { "mData": 4, "sTitle": "Authorized", "sWidth": "5%" },
        //         { "mData": 5, "sTitle": "Authorized on", "sWidth": "20%" }
        //     ]
        // });
    });

});