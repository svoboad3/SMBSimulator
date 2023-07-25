
function on(elem) {
  document.getElementById("overlay").style.display = "block";
  document.getElementById(elem).style.display = "block";
}

function off(elem) {
  document.getElementById("overlay").style.display = "none";
  document.getElementById(elem).style.display = "none";
}
function showPopup(id) {
  let popup = document.getElementById(id);
  popup.classList.toggle("show");
}

async function getExport(link){
   let data = await fetch(link)
   let content = await data.text()
   navigator.clipboard.writeText(content);
   alert("Copied export to clipboard");
}

async function deleteColumn(zone, idx){
    let deleteUrl = "/column/" + zone + "/" + idx
    await fetch(deleteUrl, {
        method: 'DELETE'
    })
    location.reload()
}

async function deleteComponent(idx){
    let deleteUrl = "/smbstation/components/" + idx
    await fetch(deleteUrl, {
        method: 'DELETE'
    })
    location.reload()
}

async function deleteSim(link){
    let response = await fetch(link, {
        method: 'DELETE'
    })
    let url = await response.text()
    window.location.href = url
}

async function postForm(formId, url){
    let form = document.getElementById(formId)
    let data = new FormData(form)
    await fetch(url,{
        "method": "POST",
        "body": data,
    })
}




