
    $(document).ready(function() {

        $('#sidebarCollapse_l').click(function() {
            $('#sidebar_l').toggleClass('active');
            var el_l = document.getElementById('sidebarCollapse_l');
            if ($('#sidebar_l').css('marginLeft')=='0px'){
                el_l.firstChild.data = "<";
            }else{
                el_l.firstChild.data = ">";
            }
        });

        $('#sidebarCollapse_r').click(function() {
            $('#sidebar_r').toggleClass('active');
            var el_r = document.getElementById('sidebarCollapse_r');
            if (el_r.firstChild.data == "<"){
                el_r.firstChild.data = ">";
            }else{
                el_r.firstChild.data = "<";
            }
        });
    });