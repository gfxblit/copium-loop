import threading

from linkify_it import LinkifyIt


def test_linkify_race_condition():
    def validate_a(_self, _text, _pos):
        return 0

    def validate_b(_self, _text, _pos):
        return 0

    errors = []

    def worker(name, validator):
        schemas = {"test:": {"validate": validator}}

        linker = LinkifyIt(schemas)

        # Check if the validator is correctly bound
        # logic in main.py: compiled["validate"] = types.MethodType(val.get("validate"), self)

        # Access internal structure to verify
        if "test:" not in linker._compiled:
            errors.append(
                f"FAIL: Schema 'test:' not found in compiled schemas for thread {name}"
            )
            return

        bound_method = linker._compiled["test:"]["validate"]

        if hasattr(LinkifyIt, "func"):
            errors.append(
                f"FAIL: LinkifyIt class polluted with 'func' attribute in thread {name}"
            )
            return

        # Check if the bound method corresponds to the correct function
        if bound_method.__func__ is not validator:
            errors.append(
                f"FAIL: Validator mismatch in thread {name}. Expected {validator}, got {bound_method.__func__}"
            )

    t1 = threading.Thread(target=worker, args=("A", validate_a))
    t2 = threading.Thread(target=worker, args=("B", validate_b))

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    if hasattr(LinkifyIt, "func"):
        errors.append(
            "FAIL: LinkifyIt class still has 'func' attribute after threads finished."
        )

    assert not errors, "\n".join(errors)
