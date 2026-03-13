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

// Tool search filter
window.filterTools = function(){
  const term = (document.getElementById("tool-search")?.value || "").toLowerCase();
  document.querySelectorAll(".tool-row").forEach(row => {
    const text = row.innerText.toLowerCase();
    row.style.display = text.includes(term) ? "" : "none";
  });
}

// Project search filter
window.filterProjects = function(){
  const term = (document.getElementById("project-search")?.value || "").toLowerCase();
  document.querySelectorAll(".project-card").forEach(card => {
    const name = card.dataset.name || "";
    card.style.display = name.includes(term) ? "" : "none";
  });
}

});
