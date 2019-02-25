// Automatically set the max-height of the note-card for each text depending on the number of texts
$(function(){
    var noteCards = $('.note-card').length;
    var max = "70vh";
    if (noteCards == 2) {
        max = "34vh";
    } else if (noteCards > 2) {
        max = "22vh";
    }
    $('.note-card').css('max-height', max);
})

// Show expand icon only if the whole note is not shown. Thanks to http://jsfiddle.net/kedem/D9NCP/
$(function() {
    $('.two-line').each(function(index, element) {
        var noteHeight = $( element ).height();
        var textHeight = $( element ).find('.card').height();
        if (textHeight < noteHeight) {
            $( element ).find('.expand').hide();
            $( element ).removeClass('fade');
        }
    });
});

// Expands and contracts the note when the expand arrow is clicked
$('.expand').click(function() {
    $('#' + $(this).attr('toExpand')).toggleClass('expanded fade');
    if ($('#' + $(this).attr('toExpand')).hasClass('fade')) {
        $(this).attr('title', expMess);
    } else {
        $(this).attr('title', conMess);
    }
});

$('.expand').each(function() {
    $(this).attr('title', expMess);
});
