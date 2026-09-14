const inspectionForm = document.querySelector("#inspectionForm");
const commentsInput = document.querySelector("#comments");
const termsCheckbox = document.querySelector("#termsAccepted");
const loadingMessage = document.querySelector("#loadingMessage");
const emptyMessage = document.querySelector("#emptyMessage");
const errorMessage = document.querySelector("#errorMessage");
const recordList = document.querySelector("#recordList");
const searchQuery = document.querySelector("#searchQuery");
const updateForm = document.querySelector("#updateForm");

const hideStatusMessages = () => {
  loadingMessage.hidden = true;
  emptyMessage.hidden = true;
  errorMessage.hidden = true;
  errorMessage.textContent = "";
};

const showLoading = () => {
  hideStatusMessages();
  recordList.replaceChildren();
  loadingMessage.hidden = false;
};

const showEmpty = () => {
  hideStatusMessages();
  recordList.replaceChildren();
  emptyMessage.hidden = false;
};

const showError = (message) => {
  hideStatusMessages();
  recordList.replaceChildren();
  errorMessage.textContent = message;
  errorMessage.hidden = false;
};

function displayRecords(records) {
  hideStatusMessages();
  recordList.replaceChildren();

  if (!records.length) {
    emptyMessage.hidden = false;
    return;
  }

  records.forEach((record) => {
    const row = document.createElement("tr");
    const idCell = document.createElement("td");
    const nameCell = document.createElement("td");
    const cuisineCell = document.createElement("td");
    idCell.textContent = record.id;
    nameCell.textContent = record.restaurantName;
    cuisineCell.textContent = record.cuisine;
    row.append(idCell, nameCell, cuisineCell);
    recordList.append(row);
  });
}

async function loadRecords(query = "") {
  showLoading();
  try {
    const params = new URLSearchParams();
    if (query) {
      params.set("q", query);
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    const response = await fetch(`/api/records${suffix}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Request failed");
    }
    displayRecords(await response.json());
  } catch (error) {
    showError("Error: Could not load inspection records.");
  }
}

function searchRecords() {
  loadRecords(searchQuery.value.trim());
}

const validateForm = () => {
  if (commentsInput.value.trim().length <= 25) {
    alert("Comments must contain more than 25 characters.");
    commentsInput.focus();
    return false;
  }

  if (!termsCheckbox.checked) {
    alert("You must agree to the terms and conditions before submitting.");
    termsCheckbox.focus();
    return false;
  }

  return true;
};

const createSubmissionCounter = () => {
  let submissionCount = 0;

  return () => {
    submissionCount += 1;
    return submissionCount;
  };
};

const trackSuccessfulSubmission = createSubmissionCounter();

async function createRecord() {
  if (!inspectionForm.reportValidity()) {
    return;
  }

  if (!validateForm()) {
    return;
  }

  const formData = new FormData(inspectionForm);
  const formObject = {
    ...Object.fromEntries(formData.entries()),
    termsAccepted: termsCheckbox.checked,
  };

  const jsonString = JSON.stringify(formObject);
  console.log("Form data JSON:", jsonString);

  const parsedObject = JSON.parse(jsonString);
  const { restaurantName, Email } = parsedObject;
  console.log("Restaurant name:", restaurantName);
  console.log("Email:", Email);

  const updatedObject = {
    ...parsedObject,
    submissionDate: new Date().toISOString(),
  };
  console.log("Updated submission:", updatedObject);

  const submissionCount = trackSuccessfulSubmission();
  console.log("Successful submission count:", submissionCount);

  try {
    const response = await fetch("/api/records", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        restaurantName: updatedObject.restaurantName,
        cuisine: updatedObject.cuisine,
        Email: updatedObject.Email,
        Comments: updatedObject.Comments,
        Result: updatedObject.Result,
        termsAccepted: updatedObject.termsAccepted,
        submissionDate: updatedObject.submissionDate,
      }),
    });

    if (!response.ok) {
      throw new Error("Could not save the inspection record.");
    }

    inspectionForm.reset();
    await loadRecords(searchQuery.value.trim());
  } catch (error) {
    showError(error.message);
  }
}

async function updateRecord() {
  if (!updateForm.reportValidity()) {
    return;
  }

  const restaurantName = document.querySelector("#updateRestaurantName").value.trim();
  const cuisine = document.querySelector("#updateCuisine").value.trim();

  try {
    const response = await fetch("/api/records/1", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ restaurantName, cuisine }),
    });

    if (!response.ok) {
      throw new Error("Could not update record 1.");
    }

    updateForm.reset();
    await loadRecords(searchQuery.value.trim());
  } catch (error) {
    showError(error.message);
  }
}

async function deleteRecord() {
  try {
    const response = await fetch("/api/records/highest", { method: "DELETE" });
    if (!response.ok) {
      throw new Error("Could not delete the highest ID.");
    }
    await loadRecords(searchQuery.value.trim());
  } catch (error) {
    showError(error.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const previewState = new URLSearchParams(window.location.search).get("state");

  if (previewState === "loading") {
    showLoading();
  } else if (previewState === "error") {
    showError("Error: Could not load inspection records.");
  } else if (previewState === "empty") {
    showEmpty();
  } else {
    const initialQuery = new URLSearchParams(window.location.search).get("q") || "";
    searchQuery.value = initialQuery;
    loadRecords(initialQuery);
  }
});
