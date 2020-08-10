
$(function() {
    $('.card.search-hit').click(function() {
        var target = $(this);
        var scrollContent = target[0].parentNode;
        var listElement = scrollContent.parentNode;
        var list = listElement.parentNode;
        for (i = 0; i < list.children.length; i++) {
            var list_of_list = list.children[i].children[1].children
            for(j = 0; j < list_of_list.length; j++){
                if(list_of_list[j].children[0].innerText == target[0].childNodes[1].innerText){
                    document.getElementById(list_of_list[j].parentNode.parentNode.attributes[0].nodeValue).scrollTop = list_of_list[j].offsetTop;
                    list_of_list[j].style.backgroundColor = "#DDDD22"
                }else{
                    list_of_list[j].style.backgroundColor = "#FFF"
                }
            }
        }
    })
})
