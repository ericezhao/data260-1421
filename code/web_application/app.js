const inspectionForm = document.querySelector("form");
const commentsInput = document.querySelector("#comments");
const termsCheckbox = document.querySelector("#termsAccepted");

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

inspectionForm.addEventListener("submit", (event) => {
  event.preventDefault();

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
  const { restaurantID, Email } = parsedObject;
  console.log("Restaurant ID:", restaurantID);
  console.log("Email:", Email);

  const updatedObject = {
    ...parsedObject,
    submissionDate: new Date().toISOString(),
  };
  console.log("Updated submission:", updatedObject);

  const submissionCount = trackSuccessfulSubmission();
  console.log("Successful submission count:", submissionCount);
});
