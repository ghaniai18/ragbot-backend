const baseURL = "https://your-app.onrender.com/login";
let selectFile = null;         
let currentFileBlobUrl = null;
async function uploadFile() {
  const fileInput = document.getElementById("fileInput");
  const file = fileInput.files[0];
  const token = localStorage.getItem("token");

  if (!file || !token) {
    alert("Missing file or token");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${baseURL}/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  const result = await response.json();
  alert(result.message || result.detail);
  
  await loadUserFiles(); 


  // if (result.file_path) {
   //await selectFile(result.file_path);
  //}
}


async function loadUserFiles() {
  const token = localStorage.getItem("token");
  const user_id = localStorage.getItem("user_id");

  const response = await fetch(`${baseURL}/start?user_id=${user_id}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });

  const files = await response.json();

  const fileList = document.getElementById("fileList"); 
  fileList.innerHTML = "";

files.forEach(file => {
  const listItem = document.createElement("li");
  listItem.className = "list-group-item list-group-item-action";
  const filePath = file.file_path || file;

  listItem.textContent = filePath.split("/").pop();
  listItem.addEventListener("click", async() => {
    selectFile = filePath;
    document.getElementById("selectedFileName").textContent = `Selected File: ${filePath.split("/").pop()}`;
    await confirmFileSelection(filePath);
    loadChatHistory(filePath); 
    await viewSelectedFile(); 


  });

  document.getElementById("fileList").appendChild(listItem);
});
}



async function viewSelectedFile() {
  const token = localStorage.getItem("token");

  try {
    const res = await fetch(`${baseURL}/viewfiles`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });

    if (!res.ok) throw new Error("Failed to fetch file");

    const viewerDiv = document.getElementById("fileViewer");

    // 🔹 Check if the response is a PDF
    const contentType = res.headers.get("content-type");

    if (contentType && contentType.includes("application/pdf")) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      viewerDiv.innerHTML = `
        <iframe src="${url}" 
                width="100%" height="800px" 
                style="border:none; display:block; margin:auto;">
        </iframe>`;
    }

    else if (contentType && contentType.includes("text/html")) {
      const html = await res.text();

      const blob = new Blob([html], { type: "text/html"});

      const url = URL.createObjectURL(blob);

      viewerDiv.innerHTML = `
        <iframe src="${url}" 
                width="100%" height="800px" 
                style="border:none; display:block; margin:auto;">
        </iframe>`;    
    } 
    else {
      // For HTML/text responses
      const content = await res.text();
      viewerDiv.innerHTML = `<pre>${content}</pre>`;
    }

    viewerDiv.style.display = "block";

  } catch (err) {
    console.error(err);
    alert("Error viewing file");
  }
} 




async function askQuestion() {
  const token = localStorage.getItem("token");
  const question = document.getElementById("questionInput").value;
  const answerBox = document.getElementById("answerBox");
  const submitButton = document.getElementById("askButton");

  if (!question || !token) {
    alert("Please enter a question or make sure you're logged in.");
    return;
  }

 
  submitButton.disabled = true;

 
  const userHTML = `<div class="mb-2 bubble-user"><strong>You:</strong> ${question}</div>`;
  answerBox.insertAdjacentHTML("beforeend", userHTML);

  
  const botThinkingId = `bot-thinking-${Date.now()}`;
  const thinkingHTML = `
    <div class="mb-3 bubble-bot" id="${botThinkingId}">
      <strong>Bot:</strong> <span id="dots">Bot is thinking<span class="dot">.</span></span>
    </div>
  `;
  answerBox.insertAdjacentHTML("beforeend", thinkingHTML);
  answerBox.scrollTop = answerBox.scrollHeight;

  
  let dotCount = 1;
  const dotsElement = document.querySelector(`#${botThinkingId} .dot`);
  const dotInterval = setInterval(() => {
    if (!dotsElement) return;
    dotCount = (dotCount % 3) + 1;
    dotsElement.innerText = ".".repeat(dotCount);
  }, 500);

  
  const formData = new URLSearchParams();
  formData.append("question", question);

  try {
    const response = await fetch(`${baseURL}/ask`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`
      },
      body: formData
    });

    const data = await response.json();

    if (response.ok) {
     
      const botHTML = `<strong>Bot:</strong> ${data.html}`;
      document.getElementById(botThinkingId).innerHTML = botHTML;
    } else {
      document.getElementById(botThinkingId).innerHTML = `<strong>Bot:</strong> Error: ${data.detail || "Something went wrong."}`;
    }
  } catch (error) {
    document.getElementById(botThinkingId).innerHTML = `<strong>Bot:</strong> Network error or backend not reachable.`;
  } finally {
    clearInterval(dotInterval);
    submitButton.disabled = false;
    document.getElementById("questionInput").value = "";
    answerBox.scrollTop = answerBox.scrollHeight;
  }
  if (!selectFile) {
  alert("Please select a file before asking a question.");
  submitButton.disabled = false;
  return;
}
}



async function loadChatHistory(selectFile){
  console.log("loadChatHistory called with:", selectFile);
  const token = localStorage.getItem("token");
  const user_id = localStorage.getItem("user_id");
  if(!selectFile || !user_id) {
    console.log("No selectedFile or user_id, aborting loadChatHistory");
    return;
  }
  const response = await fetch(`${baseURL}/history?file_path=${encodeURIComponent(selectFile)}`,{
  method: "GET",
  headers:{ Authorization: `Bearer ${token}`  },
  });
  const history = await response.json();
  console.log("Loaded chat history:",history);
  const answerBox = document.getElementById("answerBox");
  answerBox.innerHTML = "";
  
  history.chat.forEach(item =>{
    answerBox.insertAdjacentHTML("beforeend", `<div class="mb-2 bubble-user"><strong>You:</strong> ${item.question}</div>`);
    answerBox.insertAdjacentHTML("beforeend", `<div class="mb-3 bubble-bot"><strong>Bot:</strong> ${marked.parse(item.answer)}</div>`);

  });
  answerBox.scrollTop = answerBox.scrollHeight;
  }

async function onfileSelect(){
  console.log("onfileSelect called");
  await selectFile();
  const select = document.getElementById("fileSelect");
  const selectedFile = select.options[select.selectedIndex].value;
  await loadChatHistory(selectedFile);
}

async function confirmFileSelection(filePath) {
  const token = localStorage.getItem("token");
  const formData = new URLSearchParams();
  formData.append("file_path", filePath);

  const response = await fetch(`${baseURL}/select`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formData,
  });

  const result = await response.json();
  if (!response.ok) {
    alert(result.detail || "File selection failed.");
  }
}
    


  
window.onload = function () {
  loadUserFiles();

};


