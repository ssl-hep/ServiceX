$(document).ready(() => {
  $('#drequest_update_button').click((event) => {
    event.preventDefault();
    console.log('Data Access request creator called.');

    $('#name_valid').text('').show();

    const data = {};
    if ($('#name').val() === '') {
      $('#name_valid').text('Name is mandatory!').show();
      return;
    }

    data.name = $('#name').val();
    data.description = $('#description').val();
    data.dataset = $('#dataset').val();
    data.columns = $('#columns').val();
    data.events = $('#events').val();
    console.log(data);
    // call REST API to create a Data Access Request
    $.ajax({
      type: 'post',
      url: '/wrequest_update',
      contentType: 'application/json',
      data: JSON.stringify(data),
      success(link) {
        alert('It can take several minutes to get the data listed.');
        window.location.href = '/wrequest_manage';
      },
      error(xhr, textStatus, errorThrown) {
        alert(`Error code:${xhr.status}.  ${xhr.responseText}`);
        window.location.href = '/wrequest_manage';
      }
    });

  });

});
