class CineInfo:
    def __init__(self, title=None, year=None, director=None, cast=None, studio=None, composer=None, ref=None):
        self._title = title
        self._year = year
        self._director = director
        self._cast = cast if isinstance(cast, list) else [cast]
        self._studio = studio
        self._composer = composer
        self._ref = ref

    # --- title ---
    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        if not value:
            raise ValueError("Title cannot be empty")
        self._title = value

    @property
    def year(self):
        return self._year

    @year.setter
    def year(self, value):
        self._year = value

    # --- director ---
    @property
    def director(self):
        return self._director

    @director.setter
    def director(self, value):
        self._director = value

    # --- cast ---
    @property
    def cast(self):
        return self._cast

    @cast.setter
    def cast(self, value):
        if not isinstance(value, list):
            raise TypeError("Cast must be a list")
        self._cast = value

    # --- studio ---
    @property
    def studio(self):
        return self._studio

    @studio.setter
    def studio(self, value):
        self._studio = value

    # --- music director ---
    @property
    def composer(self):
        return self._composer

    @composer.setter
    def composer(self, value):
        self._composer = value

    # --- ref ---
    @property
    def ref(self):
        return self._ref

    @ref.setter
    def ref(self, value):
        self._ref = value

    # --- helper methods ---
    def add_cast_member(self, member):
        if member not in self._cast:
            self._cast.append(member)

    def remove_cast_member(self, member):
        if member in self._cast:
            self._cast.remove(member)

    def __str__(self):
        return (
            f"Album: {self._title},"
            f"Year: {self._year},"
            f"Director: {self._director},"
            f"Cast: {self._cast},"
            f"Studio: {self._studio},"
            f"Composer: {self._composer},"
            f"Ref: {self._ref}"
        )

    @property
    def __dict__(self):
        """Override __dict__ to expose clean keys without '_' prefix"""
        return {
            "title": self._title,
            "year": self._year,
            "director": self._director,
            "cast": self._cast,
            "studio": self._studio,
            "composer": self._composer,
            "ref": self._ref,
        }
