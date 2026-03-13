document.addEventListener("DOMContentLoaded", function(){

const rows = document.querySelectorAll(".tool-row");

rows.forEach(row => {

row.addEventListener("contextmenu", function(e){

e.preventDefault();

const role = row.dataset.role;

if(role === "Project Lead" || role === "Workshop Manager"){

if(confirm("Remove this tool?")){

window.location = "/remove_tool/" + row.dataset.id;

}

}

});

});

});