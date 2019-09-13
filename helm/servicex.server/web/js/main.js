
// var dropdown = function () {

// $('.has-dropdown').mouseenter(function () {

// var $this = $(this);
// $this
//   .find('.dropdown')
//   .css('display', 'block')
//   .addClass('animated-fast fadeInUpMenu');

// }).mouseleave(function () {
// var $this = $(this);

// $this
//   .find('.dropdown')
//   .css('display', 'none')
//   .removeClass('animated-fast fadeInUpMenu');
// });

// };

// var tabs = function () {

// // Auto adjust height
// $('.gtco-tab-content-wrap').css('height', 0);
// var autoHeight = function () {

//   setTimeout(function () {

//     var tabContentWrap = $('.gtco-tab-content-wrap'),
//       tabHeight = $('.gtco-tab-nav').outerHeight(),
//       formActiveHeight = $('.tab-content.active').outerHeight(),
//       totalHeight = parseInt(tabHeight + formActiveHeight + 90);

//     tabContentWrap.css('height', totalHeight);

//     $(window).resize(function () {
//       var tabContentWrap = $('.gtco-tab-content-wrap'),
//         tabHeight = $('.gtco-tab-nav').outerHeight(),
//         formActiveHeight = $('.tab-content.active').outerHeight(),
//         totalHeight = parseInt(tabHeight + formActiveHeight + 90);

//       tabContentWrap.css('height', totalHeight);
//     });

//   }, 100);

// };

// autoHeight();


// // Click tab menu
// $('.gtco-tab-nav a').on('click', function (event) {

//   var $this = $(this),
//     tab = $this.data('tab');

//   $('.tab-content')
//     .addClass('animated-fast fadeOutDown');

//   $('.tab-content')
//     .removeClass('active');

//   $('.gtco-tab-nav li').removeClass('active');

//   $this
//     .closest('li')
//     .addClass('active')

//   $this
//     .closest('.gtco-tabs')
//     .find('.tab-content[data-tab-content="' + tab + '"]')
//     .removeClass('animated-fast fadeOutDown')
//     .addClass('animated-fast active fadeIn');


//   autoHeight();
//   event.preventDefault();

// });
// };

// var loaderPage = function () {
//   $(".gtco-loader").fadeOut("slow");
// };

$('#users_button').click(() => {
  window.location.replace('/users');
});

$('#logout_button').click(() => {
  $.get('/logout');
  window.location.replace('/');
});

$('#user_delete_button').click(() => {
  // $.get('/user/delete');
  // window.location.replace('/');
});

$(document).ready(() => {

  const table1 = $('#drequests_table').DataTable({
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

  var table2 = $('#users_table').DataTable({
    paging: false,
    searching: false,
    aoColumns: [
      { mData: 0, sTitle: "Name", sWidth: "20%" },
      { mData: 1, sTitle: "Email", sWidth: "10%" },
      { mData: 2, sTitle: "Affiliation", sWidth: "20%" },
      { mData: 3, sTitle: "Registered on", sWidth: "20%" },
      { mData: 4, sTitle: "Authorized", sWidth: "5%" },
      { mData: 5, sTitle: "Authorized on", sWidth: "20%" }
    ],
  });

});