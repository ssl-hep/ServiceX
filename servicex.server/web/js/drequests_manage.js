$(document).ready(() => {

  $.getJSON('/get_requests/', (data) => {
    console.log(data);
    const table = $('#drequests_table').DataTable({
      data: data,
      paging: false,
      searching: false,
      aoColumns: [
        { mData: 0, sTitle: 'Name', sWidth: '10%' },
        { mData: 1, sTitle: 'Description', sWidth: '30%' },
        { mData: 2, sTitle: 'Created at', sWidth: '20%' },
        { mData: 3, sTitle: 'Status', sWidth: '10%' },
        { mData: 4, sTitle: 'Token', sWidth: '10%' }
      ],
    });
  });

});